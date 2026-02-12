"""
Schema分析代理
负责分析用户查询并获取相关的数据库模式信息

Skill 模式支持：
- 当 skill_context.enabled = True 时，使用 Skill 预加载的表结构
- 当 skill_context.enabled = False 时，使用全库检索模式
"""
from typing import Dict, Any, Optional, List

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage, ToolMessage, BaseMessage
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.config import get_stream_writer
from langgraph.types import Command
from typing_extensions import Annotated

from app.core.state import SQLMessageState, extract_connection_id
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.db.session import SessionLocal
from app.services.text2sql_utils import retrieve_relevant_schema, get_value_mappings, analyze_query_with_llm
from app.schemas.stream_events import create_stage_message_event, create_thought_event, create_sql_step_event


from app.agents.nodes.base import extract_new_messages_for_parent as _extract_new_messages_for_parent



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
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 立即发送 running 状态事件，让前端显示"思考中"
    writer = get_stream_writer()
    if writer:
        writer(create_sql_step_event(
            step="schema_agent",
            status="running",
            result="正在分析查询并获取相关表结构..."
        ))
        writer(create_thought_event(
            agent="schema_agent",
            thought="我正在分析您的问题，识别相关的数据表和字段...",
            plan="完成表结构分析后，将进行 SQL 生成"
        ))
    
    # 获取当前消息历史（包含 LLM 生成的 AIMessage）
    # 修复：Command.PARENT 需要包含完整消息历史，否则子 Agent 的 AIMessage 会丢失
    current_messages = list(state.get("messages", []))
    
    connection_id = state.get("connection_id") or extract_connection_id(state)
    if not connection_id:
        error_msg = ToolMessage(content="错误：未指定数据库连接", tool_call_id=tool_call_id)
        # 修复：只返回新消息，避免消息重复
        new_messages = _extract_new_messages_for_parent(current_messages, tool_call_id, error_msg)
        return Command(
            graph=Command.PARENT,
            update={"messages": new_messages}
        )
    
    # ========== Skill 模式：使用预加载的 schema，跳过全库检索 ==========
    skill_context = state.get("skill_context", {})
    if skill_context.get("enabled"):
        skill_schema_info = skill_context.get("schema_info", {})
        if skill_schema_info.get("tables"):
            # 将 Skill schema 转换为 schema_context 格式
            schema_context = {}
            for table in skill_schema_info.get("tables", []):
                table_name = table.get("table_name")
                if table_name:
                    schema_context[table_name] = {
                        "description": table.get("description", ""),
                        "columns": []
                    }
            
            for col in skill_schema_info.get("columns", []):
                table_name = col.get("table_name")
                if table_name and table_name in schema_context:
                    schema_context[table_name]["columns"].append({
                        "column_name": col.get("column_name"),
                        "data_type": col.get("data_type"),
                        "description": col.get("description", ""),
                        "is_primary_key": col.get("is_primary_key", False),
                        "is_foreign_key": col.get("is_foreign_key", False),
                    })
            
            table_count = len(schema_context)
            matched_skills = skill_context.get("matched_skills", [])
            skill_names = ", ".join(s.get("display_name", s.get("name", "未知")) for s in matched_skills)
            
            logger.info(f"[SchemaAgent] Skill 模式: {skill_names}, 表数量: {table_count}")
            
            tool_msg = ToolMessage(
                content=f"已加载业务领域 [{skill_names}] 的表结构: {table_count} 个表",
                tool_call_id=tool_call_id
            )
            # 修复：只返回新消息，避免消息重复
            new_messages = _extract_new_messages_for_parent(current_messages, tool_call_id, tool_msg)
            return Command(
                graph=Command.PARENT,
                update={
                    "schema_info": {
                        "schema_context": schema_context,
                        "skill_tables": [t.get("table_name") for t in skill_schema_info.get("tables", [])],
                        "relationships": skill_schema_info.get("relationships", []),
                        "source": "skill",
                        "skill_names": [s.get("name") for s in matched_skills],
                    },
                    "current_stage": "sql_generation",
                    "messages": new_messages
                }
            )
    
    # ========== 全库检索模式 ==========
    try:
        db = SessionLocal()
        try:
            # 1. 核心改进：优先使用 state 中已有的分析结果，避免重复 LLM 调用
            query_analysis = state.get("query_analysis")
            if not query_analysis:
                query_analysis = analyze_query_with_llm(query)
            
            # 获取相关表结构 (传入已有的分析结果)
            schema_context = retrieve_relevant_schema(
                db=db,
                connection_id=connection_id,
                query=query,
                query_analysis=query_analysis
            )
            
            # 获取值映射
            value_mappings = get_value_mappings(db, schema_context)
            table_count = len(schema_context.get("tables", [])) if isinstance(schema_context, dict) else len(schema_context)
            
            tool_msg = ToolMessage(
                content=f"已识别到 {table_count} 个相关表。分析结果：{query_analysis.get('query_intent', '')}",
                tool_call_id=tool_call_id
            )
            # 修复：只返回新消息，避免消息重复
            new_messages = _extract_new_messages_for_parent(current_messages, tool_call_id, tool_msg)
            return Command(
                graph=Command.PARENT,
                update={
                    "schema_info": {
                        "schema_context": schema_context,
                        "value_mappings": value_mappings,
                        "source": "full_schema_retrieval"
                    },
                    "query_analysis": query_analysis,  # 关键：将分析结果共享给后续 Agent
                    "current_stage": "sql_generation",
                    "messages": new_messages
                }
            )
        finally:
            db.close()
    except Exception as e:
        error_msg = ToolMessage(content=f"检索失败: {str(e)}", tool_call_id=tool_call_id)
        # 修复：只返回新消息，避免消息重复
        new_messages = _extract_new_messages_for_parent(current_messages, tool_call_id, error_msg)
        return Command(
            graph=Command.PARENT,
            update={"messages": new_messages}
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
        """创建系统提示词 - 增强推理能力"""
        system_msg = f"""你是一个专业的数据库模式分析专家。
你的任务是：深入分析用户查询，识别出回答该查询所必须的数据库表、字段以及它们之间的关联关系。

**工作原则：**
1. **语义优先**：不要只看字面意思，要理解用户查询背后的业务逻辑（例如：“最近的订单”意味着你需要订单表及其时间字段）。
2. **关联识别**：如果查询涉及多个实体，必须识别出用于 JOIN 的关联字段。
3. **输出要求**：使用 retrieve_database_schema 工具来获取实际的结构信息。在调用工具前，请简要陈述你的推理过程。

**严禁行为：**
- 严禁猜测不存在的字段。
- 严禁在没有获取到 Schema 的情况下生成 SQL 代码。
"""
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
        state["thought"] = f"检测到用户查询属于 [{skill_names}] 业务领域，我将加载预定义的行业知识库和表结构，以确保 SQL 生成符合业务逻辑。"
        state["next_plan"] = "获取表结构后，我将把任务移交给 SQL 生成专家。"
        
        # 构建消息
        table_count = len(schema_context)
        column_count = sum(len(t.get("columns", [])) for t in schema_context.values())
        
        summary = f"已加载业务领域 [{skill_names}] 的表结构: {table_count} 个表, {column_count} 个字段"
        writer = get_stream_writer()
        if writer:
            # 发送 sql_step 事件 - 关键！这是 ThinkingProcess 执行进度条的数据源
            writer(create_sql_step_event(
                step="schema_agent",
                status="completed",
                result=f"识别到 {table_count} 个相关表（Skill 模式）"
            ))
            
            # 发送思维过程事件
            writer(create_thought_event(
                agent="schema_agent",
                thought=state["thought"],
                plan=state["next_plan"]
            ))
            
            writer(create_stage_message_event(
                message=f"已完成 Schema 分析（Skill 模式），识别到 {table_count} 个相关表。",
                step="schema_agent"
            ))
        
        result = {
            "messages": [AIMessage(content=summary)],
            "schema_info": state["schema_info"],
            "current_stage": "sql_generation"
        }
        return result
    
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
        
        state["thought"] = "我正在对全库进行语义搜索，以识别与您问题最相关的表和字段。我不仅会查找字面匹配，还会通过图数据库寻找潜在的关联关系。"
        state["next_plan"] = "锁定表结构后，我将把上下文传递给 SQL 生成专家。"
        
        writer = get_stream_writer()
        if writer:
            # 发送 sql_step 事件 - 关键！
            writer(create_sql_step_event(
                step="schema_agent",
                status="completed",
                result="已完成全库 Schema 智能检索"
            ))
            
            writer(create_thought_event(
                agent="schema_agent",
                thought=state["thought"],
                plan=state["next_plan"]
            ))
            writer(create_stage_message_event(
                message="已完成全库 Schema 智能检索，准备生成 SQL。",
                step="schema_agent"
            ))
        
        return {
            "messages": result["messages"],
            "current_stage": "sql_generation"
        }


# 创建全局实例
schema_agent = SchemaAnalysisAgent()
