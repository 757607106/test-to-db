"""
智能SQL代理图 - 高级接口和图构建
专注于图的构建和便捷接口，supervisor逻辑委托给SupervisorAgent
"""
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, START, END

from app.core.state import SQLMessageState
from app.agents.agents.supervisor_agent import create_intelligent_sql_supervisor
from app.agents.agents.router_agent import route_query
from app.db.session import SessionLocal
from app.services.query_history_service import QueryHistoryService
from app.models.agent_profile import AgentProfile

def extract_connection_id_from_messages(messages) -> int:
    """从消息中提取连接ID"""
    print(f"=== 提取连接ID ===")
    print(f"消息数量: {len(messages) if messages else 0}")

    connection_id = 15  # 默认值

    # 查找最新的人类消息中的连接ID
    for message in reversed(messages):
        if hasattr(message, 'type') and message.type == 'human':
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                msg_connection_id = message.additional_kwargs.get('connection_id')
                if msg_connection_id:
                    connection_id = msg_connection_id
                    print(f"从消息中找到连接ID: {connection_id}")
                    break

    print(f"最终使用的连接ID: {connection_id}")
    print("==================")
    return connection_id


class IntelligentSQLGraph:
    """智能SQL代理图 - 高级接口"""

    def __init__(self, active_agent_profiles: List[AgentProfile] = None):
        # 使用SupervisorAgent来处理所有supervisor逻辑
        self.supervisor_agent = create_intelligent_sql_supervisor(active_agent_profiles=active_agent_profiles)
        
        # 构建顶层图
        workflow = StateGraph(SQLMessageState)
        
        workflow.add_node("router", self.router_node)
        workflow.add_node("general_chat", self.general_chat_node)
        workflow.add_node("sql_supervisor", self.sql_supervisor_node)
        
        workflow.add_edge(START, "router")
        
        workflow.add_conditional_edges(
            "router",
            lambda state: state.get("route_decision", "data_query"),
            {
                "general_chat": "general_chat",
                "data_query": "sql_supervisor"
            }
        )
        
        workflow.add_edge("general_chat", END)
        workflow.add_edge("sql_supervisor", END)
        
        self.graph = workflow.compile()

    def router_node(self, state: SQLMessageState):
        messages = state.get("messages", [])
        if not messages:
            return {"route_decision": "general_chat"}
            
        last_message = messages[-1]
        # 兼容 dict 或 Message 对象
        if isinstance(last_message, dict):
            query = last_message.get("content", "")
        else:
            query = last_message.content
            
        decision = route_query(query)
        print(f"路由决策: {decision} (Query: {query[:50]}...)")
        return {"route_decision": decision}

    def general_chat_node(self, state: SQLMessageState):
        messages = state.get("messages", [])
        # Simple LLM call
        from app.core.llms import get_default_model
        # 使用轻量级模型用于闲聊，如果配置支持的话
        llm = get_default_model()
        
        # System prompt for general chat
        system_msg = """你是一个智能数据助手。用户正在和你闲聊。
请礼貌回复，并引导用户去询问数据相关的问题（例如：'我可以帮您查询销售数据或分析用户趋势'）。
不要尝试生成 SQL 或查询数据库。"""
        
        # 构造消息列表，添加 system prompt
        chat_messages = [{"role": "system", "content": system_msg}]
        if isinstance(messages, list):
            # 转换 LangChain 消息为 dict (如果是对象)
            for m in messages:
                if isinstance(m, dict):
                    chat_messages.append(m)
                else:
                    chat_messages.append({"role": m.type, "content": m.content})
        
        try:
            response = llm.invoke(chat_messages)
            return {"messages": [response]}
        except Exception as e:
            return {"messages": [{"role": "assistant", "content": "抱歉，我目前无法回答这个问题。"}]}

    async def sql_supervisor_node(self, state: SQLMessageState):
        # 委托给 supervisor 子图
        # 动态检查 state 中的 agent_ids
        agent_ids = state.get("agent_ids")
        if agent_ids:
            print(f"检测到动态 Agent IDs: {agent_ids}，正在构建专用 Supervisor...")
            from app.crud.crud_agent_profile import agent_profile as crud_agent_profile
            from app.db.session import SessionLocal
            
            db = SessionLocal()
            try:
                profiles = []
                # agent_ids 可能是 int 列表或逗号分隔字符串
                ids_to_fetch = []
                if isinstance(agent_ids, list):
                    ids_to_fetch = agent_ids
                elif isinstance(agent_ids, str):
                    ids_to_fetch = [int(i) for i in agent_ids.split(",") if i.strip()]
                
                for aid in ids_to_fetch:
                    p = crud_agent_profile.get(db, id=aid)
                    if p: 
                        profiles.append(p)
                
                if profiles:
                    # 创建临时的 supervisor 实例
                    temp_supervisor_agent = create_intelligent_sql_supervisor(active_agent_profiles=profiles)
                    print(f"已创建包含 {len(profiles)} 个自定义专家的 Supervisor")
                    return await temp_supervisor_agent.supervisor.ainvoke(state)
            except Exception as e:
                print(f"创建动态 Supervisor 失败: {e}，回退到默认 Supervisor")
            finally:
                db.close()

        # 直接调用默认 supervisor 的 ainvoke
        return await self.supervisor_agent.supervisor.ainvoke(state)

    async def process_query(self, query: str, connection_id: int = 15) -> Dict[str, Any]:
        """处理SQL查询"""
        db = SessionLocal()
        history_service = QueryHistoryService(db)
        
        try:
            # 1. 查找相似问题 (Before Execution)
            similar_queries = []
            try:
                similar_items = history_service.find_similar_queries(query, limit=3)
                for item in similar_items:
                    similar_queries.append({
                        "query": item.query_text,
                        "created_at": item.created_at.isoformat() if item.created_at else None,
                        "meta_info": item.meta_info
                    })
            except Exception as e:
                print(f"查找相似问题失败: {e}")

            # 初始化状态
            initial_state = SQLMessageState(
                messages=[{"role": "user", "content": query}],
                connection_id=connection_id,
                current_stage="schema_analysis",
                retry_count=0,
                max_retries=3,
                error_history=[],
                similar_queries=similar_queries # 注入相似问题
            )

            # 执行图 (顶层图)
            result = await self.graph.ainvoke(initial_state)
            
            # 检查路由结果
            route_decision = result.get("route_decision")
            
            if route_decision == "general_chat":
                # 闲聊不保存查询历史，直接返回
                # 从 result['messages'] 获取最后一条回复
                messages = result.get("messages", [])
                last_msg = messages[-1] if messages else None
                response_content = last_msg.content if last_msg else ""
                
                return {
                    "success": True,
                    "result": {
                        "messages": messages,
                        "response": response_content
                    },
                    "final_stage": "general_chat",
                    "route_decision": "general_chat"
                }

            # 如果是数据查询，继续原有的处理逻辑
            # result 包含了 supervisor 执行后的状态
            
            # 2. 保存当前查询 (After Successful Execution)
            # 只有当成功时才保存，避免污染
            # 也可以根据 result 中的信息判断是否真的"成功"（例如有 generated_sql）
            graph_result = result # 这里 result 就是最终状态
            
            # 保存查询历史
            try:
                meta_info = {
                    "final_stage": graph_result.get("current_stage"),
                    "has_sql": bool(graph_result.get("generated_sql")),
                    "has_error": bool(graph_result.get("error_history"))
                }
                history_service.save_query(query, connection_id, meta_info)
            except Exception as e:
                print(f"保存查询历史失败: {e}")

            return {
                "success": True,
                "result": graph_result,
                "final_stage": graph_result.get("current_stage", "completed"),
                "similar_queries": similar_queries, # 返回给前端
                "route_decision": "data_query"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "final_stage": "error"
            }
        finally:
            db.close()

    @property
    def worker_agents(self):
        """获取工作代理列表（为了向后兼容）"""
        return self.supervisor_agent.worker_agents

# 便捷函数
def create_intelligent_sql_graph(active_agent_profiles: List[AgentProfile] = None) -> IntelligentSQLGraph:
    """创建智能SQL图实例"""
    return IntelligentSQLGraph(active_agent_profiles=active_agent_profiles)

async def process_sql_query(query: str, connection_id: int = 15, active_agent_profiles: List[AgentProfile] = None) -> Dict[str, Any]:
    """处理SQL查询的便捷函数"""
    graph = create_intelligent_sql_graph(active_agent_profiles=active_agent_profiles)
    return await graph.process_query(query, connection_id)

# 创建全局实例（为了向后兼容）
_global_graph = None


def get_global_graph():
    """获取全局图实例"""
    global _global_graph
    if _global_graph is None:
        _global_graph = create_intelligent_sql_graph()
    return _global_graph

graph = get_global_graph().graph

if __name__ == "__main__":
    # 创建图实例
    graph_instance = create_intelligent_sql_graph()
    print(f"智能SQL图创建成功: {type(graph_instance).__name__}")
    print(f"Supervisor代理: {type(graph_instance.supervisor_agent).__name__}")
    print(f"工作代理数量: {len(graph_instance.worker_agents)}")
