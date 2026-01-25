"""
LangGraph 节点模块

包含各种图节点的实现，用于构建 LangGraph 工作流。

节点分类:
1. 缓存/历史检查: thread_history_check_node, cache_check_node
2. 澄清/推荐: clarification_node, question_recommendation_node
3. Worker 节点: schema_agent_node, sql_generator_node, sql_executor_node, 
               data_analyst_node, chart_generator_node
4. 辅助节点: error_recovery_node, general_chat_node
"""

# 缓存和历史检查节点
from app.agents.nodes.thread_history_check_node import thread_history_check_node
from app.agents.nodes.cache_check_node import cache_check_node

# 澄清和推荐节点
from app.agents.nodes.clarification_node import clarification_node
from app.agents.nodes.question_recommendation_node import question_recommendation_node

# Worker 节点
from app.agents.nodes.worker_nodes import (
    schema_agent_node,
    sql_generator_node,
    sql_executor_node,
    data_analyst_node,
    chart_generator_node,
    error_recovery_node,
    general_chat_node,
    clarification_node_wrapper,
)

# 基础工具
from app.agents.nodes.base import (
    extract_user_query,
    extract_last_human_message,
    get_custom_agent,
    build_error_record,
)

__all__ = [
    # 缓存/历史
    "thread_history_check_node",
    "cache_check_node",
    # 澄清/推荐
    "clarification_node",
    "question_recommendation_node",
    # Worker 节点
    "schema_agent_node",
    "sql_generator_node",
    "sql_executor_node",
    "data_analyst_node",
    "chart_generator_node",
    "error_recovery_node",
    "general_chat_node",
    "clarification_node_wrapper",
    # 工具函数
    "extract_user_query",
    "extract_last_human_message",
    "get_custom_agent",
    "build_error_record",
]
