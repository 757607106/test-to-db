"""
Dashboard洞察分析智能体图
专门用于Dashboard数据洞察分析的LangGraph工作流
"""
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from app.agents.agents.dashboard_analyst_agent import dashboard_analyst_agent
from app.services.graph_relationship_service import graph_relationship_service


class DashboardInsightState(TypedDict):
    """Dashboard洞察分析状态"""
    dashboard: Any  # Dashboard对象
    aggregated_data: Dict[str, Any]  # 聚合数据
    relationship_context: Optional[Dict[str, Any]]  # 图谱关系
    analysis_dimensions: Optional[List[str]]  # 分析维度
    use_graph_relationships: bool  # 是否使用图谱关系
    insights: Optional[Dict[str, Any]]  # 生成的洞察
    error: Optional[str]  # 错误信息
    current_stage: str  # 当前阶段


def aggregate_data_node(state: DashboardInsightState) -> DashboardInsightState:
    """数据聚合节点"""
    print("=== 数据聚合节点 ===")
    state["current_stage"] = "data_aggregation"
    # 这里的聚合逻辑已在service层完成，此节点主要用于状态流转
    print(f"聚合数据行数: {state['aggregated_data'].get('total_rows', 0)}")
    return state


def query_relationships_node(state: DashboardInsightState) -> DashboardInsightState:
    """查询图谱关系节点"""
    print("=== 查询图谱关系节点 ===")
    state["current_stage"] = "relationship_query"
    
    if not state.get("use_graph_relationships", False):
        print("未启用图谱关系分析，跳过")
        state["relationship_context"] = None
        return state
    
    table_names = state["aggregated_data"].get("table_names", [])
    if not table_names:
        print("未找到表名，跳过图谱查询")
        state["relationship_context"] = None
        return state
    
    try:
        # 获取connection_id（从aggregated_data中）
        connection_id = state["aggregated_data"].get("connection_id", 1)
        relationship_context = graph_relationship_service.query_table_relationships(
            connection_id,
            table_names
        )
        state["relationship_context"] = relationship_context
        print(f"发现 {relationship_context.get('relationship_count', 0)} 个表关系")
    except Exception as e:
        print(f"图谱查询失败: {str(e)}")
        state["relationship_context"] = None
    
    return state


def analyze_insights_node(state: DashboardInsightState) -> DashboardInsightState:
    """AI洞察分析节点"""
    print("=== AI洞察分析节点 ===")
    state["current_stage"] = "insight_analysis"
    
    try:
        insights = dashboard_analyst_agent.analyze_dashboard_data(
            dashboard=state["dashboard"],
            aggregated_data=state["aggregated_data"],
            relationship_context=state.get("relationship_context"),
            analysis_dimensions=state.get("analysis_dimensions")
        )
        
        # 转换为字典格式
        state["insights"] = insights.dict(exclude_none=True)
        state["error"] = None
        print("洞察分析完成")
        
    except Exception as e:
        error_msg = f"AI洞察分析失败: {str(e)}"
        print(error_msg)
        state["error"] = error_msg
        
        # 使用降级方案
        state["insights"] = {
            "summary": {
                "total_rows": state["aggregated_data"].get("total_rows", 0),
                "key_metrics": {},
                "time_range": "分析失败"
            },
            "trends": None,
            "anomalies": [],
            "correlations": [],
            "recommendations": [
                {
                    "type": "warning",
                    "content": "洞察分析遇到问题，请稍后重试",
                    "priority": "high"
                }
            ]
        }
    
    return state


def should_query_relationships(state: DashboardInsightState) -> str:
    """判断是否需要查询图谱关系"""
    if state.get("use_graph_relationships", False):
        return "query_relationships"
    return "analyze_insights"


# 构建工作流图
def create_dashboard_insight_graph():
    """创建Dashboard洞察分析图"""
    
    workflow = StateGraph(DashboardInsightState)
    
    # 添加节点
    workflow.add_node("aggregate_data", aggregate_data_node)
    workflow.add_node("query_relationships", query_relationships_node)
    workflow.add_node("analyze_insights", analyze_insights_node)
    
    # 设置入口点
    workflow.set_entry_point("aggregate_data")
    
    # 添加边
    workflow.add_conditional_edges(
        "aggregate_data",
        should_query_relationships,
        {
            "query_relationships": "query_relationships",
            "analyze_insights": "analyze_insights"
        }
    )
    
    workflow.add_edge("query_relationships", "analyze_insights")
    workflow.add_edge("analyze_insights", END)
    
    # 编译图
    graph = workflow.compile()
    return graph


# 创建全局图实例
dashboard_insight_graph = create_dashboard_insight_graph()


# 便捷函数
async def analyze_dashboard(
    dashboard: Any,
    aggregated_data: Dict[str, Any],
    use_graph_relationships: bool = True,
    analysis_dimensions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    分析Dashboard的便捷函数
    
    Args:
        dashboard: Dashboard对象
        aggregated_data: 聚合数据
        use_graph_relationships: 是否使用图谱关系
        analysis_dimensions: 分析维度
        
    Returns:
        洞察结果
    """
    initial_state = DashboardInsightState(
        dashboard=dashboard,
        aggregated_data=aggregated_data,
        relationship_context=None,
        analysis_dimensions=analysis_dimensions,
        use_graph_relationships=use_graph_relationships,
        insights=None,
        error=None,
        current_stage="initialized"
    )
    
    result = await dashboard_insight_graph.ainvoke(initial_state)
    
    return {
        "insights": result.get("insights"),
        "relationship_context": result.get("relationship_context"),
        "error": result.get("error")
    }


if __name__ == "__main__":
    print("Dashboard洞察分析图创建成功")
    print(f"图节点: {dashboard_insight_graph.get_graph().nodes}")
