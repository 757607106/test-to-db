"""
Supervisor 防护机制

提供运行时防护，确保系统稳定：
- 最大轮次限制：防止无限循环
- 循环检测：避免同一 Agent 被重复调用
- 状态验证：确保关键前置条件满足

设计原则：
- 不干预 LLM 决策逻辑
- 只在边界条件触发时介入
- 提供清晰的错误信息
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# ===== 防护配置 =====
MAX_SUPERVISOR_TURNS = 15  # 最大调用轮次
MAX_SAME_AGENT_CONSECUTIVE = 3  # 同一 Agent 最大连续调用次数
REQUIRED_STAGES_FOR_SQL = ["schema_analysis"]  # 生成 SQL 前必须完成的阶段


def check_turn_limit(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查是否达到最大轮次限制
    
    Returns:
        {"should_stop": bool, "reason": str} 如果应该停止
        {} 如果可以继续
    """
    turn_count = state.get("supervisor_turn_count", 0)
    
    if turn_count >= MAX_SUPERVISOR_TURNS:
        logger.warning(f"达到最大轮次限制: {turn_count}/{MAX_SUPERVISOR_TURNS}")
        return {
            "should_stop": True,
            "reason": f"已达到最大调用轮次限制 ({MAX_SUPERVISOR_TURNS})，请简化查询或联系管理员"
        }
    
    return {}


def check_agent_loop(state: Dict[str, Any], current_agent: str) -> Dict[str, Any]:
    """
    检测是否存在 Agent 调用循环
    
    Args:
        state: 当前状态
        current_agent: 即将调用的 Agent 名称
    
    Returns:
        {"should_stop": bool, "reason": str} 如果检测到循环
        {} 如果可以继续
    """
    agent_call_history = state.get("agent_call_history", [])
    
    if not agent_call_history:
        return {}
    
    # 检查连续调用同一 Agent
    consecutive_count = 0
    for agent in reversed(agent_call_history):
        if agent == current_agent:
            consecutive_count += 1
        else:
            break
    
    if consecutive_count >= MAX_SAME_AGENT_CONSECUTIVE:
        logger.warning(f"Agent 循环检测: {current_agent} 连续调用 {consecutive_count} 次")
        return {
            "should_stop": True,
            "reason": f"检测到 {current_agent} 被连续调用 {consecutive_count} 次，可能存在循环"
        }
    
    return {}


def check_prerequisites(state: Dict[str, Any], target_agent: str) -> Dict[str, Any]:
    """
    检查调用目标 Agent 的前置条件
    
    Args:
        state: 当前状态
        target_agent: 目标 Agent 名称
    
    Returns:
        {"should_stop": bool, "reason": str, "suggestion": str} 如果前置条件不满足
        {} 如果可以继续
    """
    completed_stages = state.get("completed_stages", [])
    
    # SQL Generator 需要先完成 Schema 分析
    if target_agent == "sql_generator_agent":
        if "schema_analysis" not in completed_stages and not state.get("schema_info"):
            return {
                "should_stop": True,
                "reason": "生成 SQL 前需要先获取数据库结构信息",
                "suggestion": "请先调用 schema_agent 获取相关表结构"
            }
    
    # SQL Executor 需要先有 SQL
    if target_agent == "sql_executor_agent":
        if not state.get("generated_sql"):
            return {
                "should_stop": True,
                "reason": "执行 SQL 前需要先生成 SQL 语句",
                "suggestion": "请先调用 sql_generator_agent 生成 SQL"
            }
    
    # Data Analyst 需要先有执行结果
    if target_agent == "data_analyst_agent":
        if not state.get("execution_result"):
            return {
                "should_stop": True,
                "reason": "数据分析前需要先有查询结果",
                "suggestion": "请先调用 sql_executor_agent 执行查询"
            }
    
    return {}


def run_all_guards(state: Dict[str, Any], target_agent: Optional[str] = None) -> Dict[str, Any]:
    """
    运行所有防护检查
    
    Args:
        state: 当前状态
        target_agent: 目标 Agent（可选）
    
    Returns:
        防护检查结果，包含 should_stop、reason 等字段
    """
    # 1. 轮次限制检查
    result = check_turn_limit(state)
    if result.get("should_stop"):
        return result
    
    # 2. Agent 循环检测
    if target_agent:
        result = check_agent_loop(state, target_agent)
        if result.get("should_stop"):
            return result
        
        # 3. 前置条件检查
        result = check_prerequisites(state, target_agent)
        if result.get("should_stop"):
            return result
    
    return {"should_stop": False}


def update_guard_state(
    state: Dict[str, Any], 
    agent_name: str,
    completed_stage: Optional[str] = None
) -> Dict[str, Any]:
    """
    更新防护相关的状态字段
    
    Args:
        state: 当前状态
        agent_name: 刚调用的 Agent 名称
        completed_stage: 完成的阶段（可选）
    
    Returns:
        需要更新的状态字段
    """
    updates = {}
    
    # 更新轮次计数
    updates["supervisor_turn_count"] = state.get("supervisor_turn_count", 0) + 1
    
    # 更新最后调用的 Agent
    updates["last_agent_called"] = agent_name
    
    # 更新调用历史
    agent_call_history = list(state.get("agent_call_history", []))
    agent_call_history.append(agent_name)
    # 只保留最近 20 条记录
    if len(agent_call_history) > 20:
        agent_call_history = agent_call_history[-20:]
    updates["agent_call_history"] = agent_call_history
    
    # 更新完成的阶段
    if completed_stage:
        completed_stages = list(state.get("completed_stages", []))
        if completed_stage not in completed_stages:
            completed_stages.append(completed_stage)
        updates["completed_stages"] = completed_stages
    
    return updates


# Agent 名称到阶段的映射
AGENT_TO_STAGE_MAP = {
    "schema_agent": "schema_analysis",
    "clarification_agent": "clarification",
    "sql_generator_agent": "sql_generation",
    "sql_validator_agent": "sql_validation",
    "sql_executor_agent": "sql_execution",
    "data_analyst_agent": "data_analysis",
    "chart_generator_agent": "chart_generation",
    "error_recovery_agent": "error_recovery",
}


def get_stage_for_agent(agent_name: str) -> Optional[str]:
    """获取 Agent 对应的阶段名称"""
    return AGENT_TO_STAGE_MAP.get(agent_name)
