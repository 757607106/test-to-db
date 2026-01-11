"""
Schema分析代理
负责分析用户查询并获取相关的数据库模式信息
"""
from typing import Dict, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, extract_connection_id
from app.core.llms import get_default_model
from app.db.session import SessionLocal
from app.services.text2sql_utils import retrieve_relevant_schema, get_value_mappings, analyze_query_with_llm

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
def retrieve_database_schema(query: str, connection_id: int) -> Dict[str, Any]:
    """
    根据查询分析结果获取相关的数据库表结构信息

    Args:
        query: 用户查询
        connection_id: 数据库连接ID

    Returns:
        相关的表结构和值映射信息
    """

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
            
            return {
                "success": True,
                "schema_context": schema_context,
                "value_mappings": value_mappings
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

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
        self.llm = get_default_model()
        self.tools = [analyze_user_query, retrieve_database_schema] #, validate_schema_completeness]

        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt,  # 动态提示词
            name=self.name,
        )
    
    def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
        connection_id = extract_connection_id(state)

        """创建系统提示"""
        system_msg = f"""你是一个专业的数据库模式分析专家。
        **重要：当前数据库connection_id是 {connection_id}**
你的任务是：
1. 分析用户的自然语言查询，理解其意图和涉及的实体
2. 获取与查询相关的数据库表结构信息
3. 验证获取的模式信息是否足够完整

工作流程：
1. 首先使用 analyze_user_query 工具分析用户查询
2. 然后使用 retrieve_database_schema 工具获取相关表结构

请确保：
- 准确理解用户查询意图
- 获取所有相关的表和字段信息
- 包含必要的值映射信息
- 验证信息的完整性

如果发现信息不完整，请提供具体的建议。"""

        return [{"role": "system", "content": system_msg}] + state["messages"]

    # 3. 最后使用 validate_schema_completeness 工具验证信息完整性

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理Schema分析任务"""
        try:
            # 获取用户查询
            user_query = state["messages"][-1].content
            if isinstance(user_query, list):
                user_query = user_query[0]["text"]
            
            # 获取connection_id
            connection_id = state.get("connection_id", 15)

            # 准备输入消息，包含connection_id信息
            messages = [
                HumanMessage(content=f"""请分析以下用户查询并获取相关的数据库模式信息：{user_query}

重要：当前数据库连接ID是 {connection_id}，在调用 retrieve_database_schema 工具时，必须传递 connection_id={connection_id} 参数。""")
            ]

            # 调用代理
            result = await self.agent.ainvoke({
                "messages": messages
            })
            
            # 更新状态
            state["current_stage"] = "sql_generation"
            state["agent_messages"]["schema_agent"] = result
            
            return {
                "messages": result["messages"],
                "current_stage": "sql_generation"
            }
            
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

# pragma: no cover  My80OmFIVnBZMlhva3JMbW5iN21ucGM2WkZWNFpRPT06MDEwM2VlYzQ=

# 创建全局实例
schema_agent = SchemaAnalysisAgent()
