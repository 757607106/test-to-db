"""
Schema分析代理 - 优化版
负责分析用户查询并获取相关的数据库模式信息
优化：改为直接工具调用模式，避免ReAct开销
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


# 合并为单个工具函数，减少调用次数
@tool
def analyze_query_and_fetch_schema(query: str, connection_id: int) -> Dict[str, Any]:
    """
    一次性分析查询并获取相关schema - 优化版
    
    Args:
        query: 用户的自然语言查询
        connection_id: 数据库连接ID
        
    Returns:
        包含查询分析、schema上下文和值映射的完整结果
    """
    try:
        # 分析查询
        print(f"开始分析用户查询: {query[:50]}...")
        analysis = analyze_query_with_llm(query)
        
        # 获取schema
        db = SessionLocal()
        try:
            schema_context = retrieve_relevant_schema(
                db=db,
                connection_id=connection_id,
                query=query
            )
            
            value_mappings = get_value_mappings(db, schema_context)
            
            return {
                "success": True,
                "query_analysis": analysis,
                "schema_context": schema_context,
                "value_mappings": value_mappings,
                "connection_id": connection_id
            }
        finally:
            db.close()
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# 旧工具函数已被analyze_query_and_fetch_schema替代（已禁用）
# @tool
# def analyze_user_query(query: str) -> Dict[str, Any]:
#     """分析用户的自然语言查询 - 已被analyze_query_and_fetch_schema替代"""
#     pass
# 
# 
# @tool
# def retrieve_database_schema(query: str, connection_id: int) -> Dict[str, Any]:
#     """获取相关的数据库表结构信息 - 已被analyze_query_and_fetch_schema替代"""
#     pass

# 已禁用：查询建议功能
# @tool
# def validate_schema_completeness(schema_info: Dict[str, Any], query_analysis: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     验证获取的模式信息是否足够完整来回答用户查询
#     
#     Args:
#         schema_info: 获取的模式信息
#         query_analysis: 查询分析结果
#         
#     Returns:
#         验证结果和建议
#     """
#     try:
#         # 检查是否有足够的表信息
#         required_entities = query_analysis.get("entities", [])
#         available_tables = list(schema_info.get("schema_context", {}).keys())
#         
#         missing_entities = []
#         for entity in required_entities:
#             # 简单的匹配逻辑，可以进一步优化
#             if not any(entity.lower() in table.lower() for table in available_tables):
#                 missing_entities.append(entity)
#         
#         is_complete = len(missing_entities) == 0
#         
#         suggestions = []
#         if missing_entities:
#             suggestions.append(f"可能缺少与以下实体相关的表信息: {', '.join(missing_entities)}")
#         
#         return {
#             "success": True,
#             "is_complete": is_complete,
#             "missing_entities": missing_entities,
#             "suggestions": suggestions
#         }
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e)
#         }


class SchemaAnalysisAgent:
    """Schema分析代理 - 优化版（直接工具调用模式）"""

    def __init__(self):
        self.name = "schema_agent"
        self.llm = get_default_model()
        # 简化：只使用一个合并的工具
        self.tools = [analyze_query_and_fetch_schema]

        # 保留ReAct代理以兼容supervisor（但实际不使用ReAct循环）
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt,
            name=self.name,
        )
    
    def _create_system_prompt(self, state: SQLMessageState, config: RunnableConfig) -> list[AnyMessage]:
        """创建系统提示 - 简化版"""
        connection_id = extract_connection_id(state)

        system_msg = f"""你是一个高效的数据库模式分析专家。
**重要：当前数据库connection_id是 {connection_id}**

你的任务是快速获取相关的数据库表结构信息：

工作流程（简化）：
1. 使用 analyze_query_and_fetch_schema 工具一次性完成分析和schema获取

请确保：
- 准确理解用户查询意图
- 获取所有相关的表和字段信息
- 包含必要的值映射信息

请快速执行。"""

        return [{"role": "system", "content": system_msg}] + state["messages"]

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理Schema分析任务 - 优化版（直接工具调用）"""
        try:
            # 获取用户查询
            user_query = state["messages"][-1].content
            if isinstance(user_query, list):
                user_query = user_query[0]["text"]
            
            # 获取connection_id
            connection_id = state.get("connection_id", 15)

            # 直接调用工具函数，避免ReAct循环
            print(f"直接调用schema工具: connection_id={connection_id}")
            result = analyze_query_and_fetch_schema.invoke({
                "query": user_query,
                "connection_id": connection_id
            })
            
            if not result.get("success"):
                raise ValueError(result.get("error", "Schema分析失败"))
            
            # 更新状态
            state["schema_info"] = result
            state["current_stage"] = "sql_generation"
            
            # 构造简单的消息响应
            summary_msg = f"已获取相关schema信息，包含{len(result.get('schema_context', {}))}个表"
            
            return {
                "messages": [AIMessage(content=summary_msg)],
                "schema_info": result,
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


# 创建全局实例
schema_agent = SchemaAnalysisAgent()
