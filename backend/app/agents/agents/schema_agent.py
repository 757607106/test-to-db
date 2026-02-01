"""
Schema分析代理
负责分析用户查询并获取相关的数据库模式信息

Skill 模式支持：
- 当 skill_context.enabled = True 时，使用 Skill 预加载的表结构
- 当 skill_context.enabled = False 时，使用全库检索模式
"""
from typing import Dict, Any, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage, ToolMessage
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.config import get_stream_writer
from langgraph.types import Command
from typing_extensions import Annotated

from app.core.state import SQLMessageState, extract_connection_id
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.db.session import SessionLocal
from app.services.text2sql_utils import retrieve_relevant_schema, get_value_mappings, analyze_query_with_llm
from app.schemas.stream_events import create_stage_message_event


@tool
def analyze_user_query(query: str) -> Dict[str, Any]:
    """
    分析用户的自然语言查询，提取关键实体和意图
    
    Args:
        query: 用户的自然语言查询
        
    Returns:
        包含实体、关系和查询意图的分析结果
    """
    try:
        analysis = analyze_query_with_llm(query)
        return {
            "success": True,
            "analysis": analysis
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@tool
def retrieve_database_schema(
    query: str, 
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    根据查询分析结果获取相关的数据库表结构信息
    
    Args:
        query: 用户查询
    
    Returns:
        Command: 更新父图状态的命令
    """
    # 优先从 state 直接获取，如果没有则从 messages 中提取
    connection_id = state.get("connection_id")
    if not connection_id:
        connection_id = extract_connection_id(state)
    if not connection_id:
        return Command(
            graph=Command.PARENT,
            update={
                "messages": [ToolMessage(
                    content="错误：未指定数据库连接，请先在界面中选择一个数据库",
                    tool_call_id=tool_call_id
                )]
            }
        )
    
    print("开始分析用户查询...", connection_id)
    try:
        db = SessionLocal()
        try:
            # 获取相关表结构
            schema_context = retrieve_relevant_schema(
                db=db,
                connection_id=connection_id,
                query=query
            )
            
            # 获取值映射
            value_mappings = get_value_mappings(db, schema_context)
            
            table_count = len(schema_context) if schema_context else 0
            
            # 返回 Command 更新父图状态（关键：graph=Command.PARENT）
            return Command(
                graph=Command.PARENT,
                update={
                    "schema_info": {
                        "schema_context": schema_context,
                        "value_mappings": value_mappings,
                        "source": "full_schema_retrieval"
                    },
                    "current_stage": "sql_generation",
                    "messages": [ToolMessage(
                        content=f"已获取 {table_count} 个相关表的结构信息，可以继续生成 SQL",
                        tool_call_id=tool_call_id
                    )]
                }
            )
        finally:
            db.close()
    except Exception as e:
        return Command(
            graph=Command.PARENT,
            update={
                "messages": [ToolMessage(
                    content=f"获取数据库结构失败: {str(e)}",
                    tool_call_id=tool_call_id
                )]
            }
        )


@tool
def validate_schema_completeness(schema_info: Dict[str, Any], query_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证获取的模式信息是否足够完整来回答用户查询
    
    Args:
        schema_info: 获取的模式信息
        query_analysis: 查询分析结果
        
    Returns:
        验证结果和建议
    """
    try:
        # 检查是否有足够的表信息
        required_entities = query_analysis.get("entities", [])
        available_tables = list(schema_info.get("schema_context", {}).keys())
        
        missing_entities = []
        for entity in required_entities:
            # 简单的匹配逻辑，可以进一步优化
            if not any(entity.lower() in table.lower() for table in available_tables):
                missing_entities.append(entity)
        
        is_complete = len(missing_entities) == 0
        
        suggestions = []
        if missing_entities:
            suggestions.append(f"可能缺少与以下实体相关的表信息: {', '.join(missing_entities)}")
        
        return {
            "success": True,
            "is_complete": is_complete,
            "missing_entities": missing_entities,
            "suggestions": suggestions
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


class SchemaAnalysisAgent:
    """Schema分析代理"""

    def __init__(self):
        self.name = "schema_agent"  # 添加name属性
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [analyze_user_query, retrieve_database_schema]

        # 创建ReAct代理（使用自定义 state_schema 以支持 connection_id 等字段）
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt,  # 动态提示词
            name=self.name,
            state_schema=SQLMessageState,  # 官方推荐：让子 agent 使用相同的 state schema
        )
    
    def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
        """创建系统提示"""
        system_msg = f"""你是一个专业的数据库模式分析专家。

你的唯一任务是：获取与用户查询相关的数据库表结构信息。

工作流程：
1. 使用 analyze_user_query 工具分析用户查询
2. 使用 retrieve_database_schema 工具获取相关表结构

**严格限制（必须遵守）：**
- **只输出表结构信息**，不要给任何建议、解释或"查询逻辑"。
- **严禁问用户问题**。澄清由系统其他模块处理，你不需要关心。
- **严禁设定默认值**。如果用户说"最近"，你只需获取相关的日期字段，不要猜测范围。
- **严禁输出"建议的查询逻辑"**。你的职责仅限于获取 schema，不负责规划查询。

输出格式：
- 只需简洁列出找到的相关表和字段
- 不要解释如何使用这些字段
- 不要给出任何建议"""

        return [{"role": "system", "content": system_msg}] + state["messages"]

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        处理Schema分析任务
        
        流程：
        1. 检查是否有 skill_context（Skill 模式）
        2. Skill 模式：直接使用预加载的 schema，跳过检索
        3. 全库模式：调用 ReAct Agent 进行检索
        """
        try:
            # 获取用户查询
            user_query = state["messages"][-1].content
            if isinstance(user_query, list):
                user_query = user_query[0]["text"]
            
            # 获取 connection_id：优先从 state 直接获取，如果没有则从 messages 中提取
            connection_id = state.get("connection_id") or extract_connection_id(state)
            if not connection_id:
                return {
                    "messages": [AIMessage(content="请先选择一个数据库连接")],
                    "current_stage": "error_recovery"
                }
            
            # 检查 Skill 模式
            skill_context = state.get("skill_context", {})
            
            if skill_context.get("enabled"):
                # Skill 模式：直接使用预加载的 schema
                return await self._process_with_skill(state, skill_context, user_query)
            else:
                # 全库模式：使用 ReAct Agent 检索
                return await self._process_full_schema(state, user_query, connection_id)
            
        except Exception as e:
            # 记录错误
            error_info = {
                "stage": "schema_analysis",
                "error": str(e),
                "retry_count": state.get("retry_count", 0)
            }
            
            state["error_history"].append(error_info)
            state["current_stage"] = "error_recovery"
            
            return {
                "messages": [AIMessage(content=f"Schema分析失败: {str(e)}")],
                "current_stage": "error_recovery"
            }
    
    async def _process_with_skill(
        self, 
        state: SQLMessageState, 
        skill_context: Dict[str, Any],
        user_query: str
    ) -> Dict[str, Any]:
        """
        Skill 模式：使用预加载的 schema
        
        优势：
        - 跳过检索步骤，更快
        - 表范围精确，减少 token 消耗
        - 包含业务规则和 JOIN 规则
        """
        import logging
        logger = logging.getLogger(__name__)
        
        schema_info = skill_context.get("schema_info", {})
        matched_skills = skill_context.get("matched_skills", [])
        
        skill_names = ", ".join(s.get("display_name", s.get("name", "未知")) for s in matched_skills)
        logger.info(f"[SchemaAgent] Skill 模式: {skill_names}, 表数量: {len(schema_info.get('tables', []))}")
        
        # 构建 schema_context 格式（与全库检索一致）
        schema_context = {}
        for table in schema_info.get("tables", []):
            table_name = table.get("table_name")
            if table_name:
                schema_context[table_name] = {
                    "description": table.get("description", ""),
                    "columns": []
                }
        
        # 添加列信息
        for col in schema_info.get("columns", []):
            table_name = col.get("table_name")
            if table_name and table_name in schema_context:
                schema_context[table_name]["columns"].append({
                    "column_name": col.get("column_name"),
                    "data_type": col.get("data_type"),
                    "description": col.get("description", ""),
                    "is_primary_key": col.get("is_primary_key", False),
                    "is_foreign_key": col.get("is_foreign_key", False),
                })
        
        # 更新状态
        state["schema_info"] = {
            "schema_context": schema_context,
            "skill_tables": [t.get("table_name") for t in schema_info.get("tables", [])],
            "relationships": schema_info.get("relationships", []),
            "source": "skill",
            "skill_names": [s.get("name") for s in matched_skills],
        }
        state["current_stage"] = "sql_generation"
        
        # 构建消息
        table_count = len(schema_context)
        column_count = sum(len(t.get("columns", [])) for t in schema_context.values())
        
        summary = f"已加载业务领域 [{skill_names}] 的表结构: {table_count} 个表, {column_count} 个字段"
        writer = get_stream_writer()
        if writer:
            writer(create_stage_message_event(
                message=f"已完成 Schema 分析（Skill 模式），识别到 {table_count} 个相关表。",
                step="schema_agent"
            ))
        
        return {
            "messages": [AIMessage(content=summary)],
            "schema_info": state["schema_info"],
            "current_stage": "sql_generation"
        }
    
    async def _process_full_schema(
        self, 
        state: SQLMessageState, 
        user_query: str,
        connection_id: int
    ) -> Dict[str, Any]:
        """
        全库模式：使用 ReAct Agent 检索相关表结构
        """
        # 准备输入消息
        messages = [
            HumanMessage(content=f"请分析以下用户查询并获取相关的数据库模式信息：{user_query}")
        ]

        # 调用代理
        result = await self.agent.ainvoke({
            "messages": messages
        })
        
        # 更新状态
        state["current_stage"] = "sql_generation"
        state["agent_messages"]["schema_agent"] = result
        writer = get_stream_writer()
        if writer:
            writer(create_stage_message_event(
                message="已完成 Schema 分析，准备生成 SQL。",
                step="schema_agent"
            ))
        
        return {
            "messages": result["messages"],
            "current_stage": "sql_generation"
        }


# 创建全局实例
schema_agent = SchemaAnalysisAgent()
