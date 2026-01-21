"""
错误恢复代理
负责分析错误、提供恢复策略和自动修复能力
"""
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.schemas.agent_message import ToolResponse


@tool
def analyze_error_pattern(error_history: List[Dict[str, Any]]) -> ToolResponse:
    """
    分析错误模式，识别重复错误和根本原因
    
    Args:
        error_history: 错误历史记录
        
    Returns:
        错误模式分析结果
    """
    try:
        if not error_history:
            return ToolResponse(
                status="success",
                data={
                    "pattern_found": False,
                    "message": "没有错误历史记录"
                }
            )
        
        # 统计错误类型
        error_types = {}
        error_stages = {}
        
        for error in error_history:
            error_msg = error.get("error", "").lower()
            stage = error.get("stage", "unknown")
            
            # 分类错误类型
            if "syntax" in error_msg or "语法" in error_msg:
                error_types["syntax_error"] = error_types.get("syntax_error", 0) + 1
            elif "connection" in error_msg or "连接" in error_msg:
                error_types["connection_error"] = error_types.get("connection_error", 0) + 1
            elif "permission" in error_msg or "权限" in error_msg:
                error_types["permission_error"] = error_types.get("permission_error", 0) + 1
            elif "timeout" in error_msg or "超时" in error_msg:
                error_types["timeout_error"] = error_types.get("timeout_error", 0) + 1
            else:
                error_types["unknown_error"] = error_types.get("unknown_error", 0) + 1
            
            # 统计错误阶段
            error_stages[stage] = error_stages.get(stage, 0) + 1
        
        # 识别模式
        most_common_type = max(error_types.items(), key=lambda x: x[1]) if error_types else ("none", 0)
        most_common_stage = max(error_stages.items(), key=lambda x: x[1]) if error_stages else ("none", 0)
        
        pattern_found = most_common_type[1] > 1 or most_common_stage[1] > 1
        
        return ToolResponse(
            status="success",
            data={
                "pattern_found": pattern_found,
                "error_types": error_types,
                "error_stages": error_stages,
                "most_common_type": most_common_type[0],
                "most_common_stage": most_common_stage[0],
                "total_errors": len(error_history)
            }
        )
        
    except Exception as e:
        return ToolResponse(
            status="error",
            error=str(e)
        )


@tool
def generate_recovery_strategy(error_analysis: Dict[str, Any], current_state: Dict[str, Any]) -> ToolResponse:
    """
    基于错误分析生成恢复策略
    
    Args:
        error_analysis: 错误分析结果
        current_state: 当前状态信息
        
    Returns:
        恢复策略建议
    """
    try:
        most_common_type = error_analysis.get("most_common_type", "unknown")
        most_common_stage = error_analysis.get("most_common_stage", "unknown")
        retry_count = current_state.get("retry_count", 0)
        
        # 基于错误类型制定策略
        strategies = {
            "syntax_error": {
                "primary_action": "regenerate_sql_with_constraints",
                "secondary_action": "simplify_query",
                "description": "SQL语法错误，需要重新生成或简化查询",
                "auto_fixable": True,
                "confidence": 0.8
            },
            "connection_error": {
                "primary_action": "check_database_connection",
                "secondary_action": "use_alternative_connection",
                "description": "数据库连接问题，需要检查连接配置",
                "auto_fixable": False,
                "confidence": 0.6
            },
            "permission_error": {
                "primary_action": "modify_query_scope",
                "secondary_action": "request_elevated_permissions",
                "description": "权限不足，需要修改查询范围或提升权限",
                "auto_fixable": False,
                "confidence": 0.4
            },
            "timeout_error": {
                "primary_action": "optimize_query_performance",
                "secondary_action": "add_query_limits",
                "description": "查询超时，需要优化性能或添加限制",
                "auto_fixable": True,
                "confidence": 0.7
            }
        }
        
        strategy = strategies.get(most_common_type, {
            "primary_action": "restart_from_beginning",
            "secondary_action": "manual_intervention",
            "description": "未知错误类型，建议重新开始或人工干预",
            "auto_fixable": False,
            "confidence": 0.3
        })
        
        # 调整策略基于重试次数
        if retry_count >= 2:
            strategy["primary_action"] = strategy["secondary_action"]
            strategy["confidence"] *= 0.7
        
        # 添加具体的恢复步骤
        recovery_steps = []
        if strategy["primary_action"] == "regenerate_sql_with_constraints":
            recovery_steps = [
                "重新分析用户查询意图",
                "使用更严格的SQL生成约束",
                "验证生成的SQL语法",
                "测试SQL执行"
            ]
        elif strategy["primary_action"] == "optimize_query_performance":
            recovery_steps = [
                "分析查询复杂度",
                "添加适当的LIMIT子句",
                "优化JOIN操作",
                "考虑使用索引提示"
            ]
        elif strategy["primary_action"] == "simplify_query":
            recovery_steps = [
                "分解复杂查询为简单查询",
                "移除非必要的JOIN",
                "减少查询字段数量",
                "添加基本的过滤条件"
            ]
        
        return ToolResponse(
            status="success",
            data={
                "strategy": strategy,
                "recovery_steps": recovery_steps,
                "estimated_success_rate": strategy["confidence"]
            }
        )
        
    except Exception as e:
        return ToolResponse(
            status="error",
            error=str(e)
        )


# ============================================================================
# 已移除 auto_fix_sql_error 工具（2026-01-21）
# 原因：自动修复逻辑过于简单（添加分号、修正大小写等），修复成功率很低
# 建议方案：分析错误后重新生成 SQL，而不是尝试自动修复
# ============================================================================


class ErrorRecoveryAgent:
    """错误恢复代理"""

    def __init__(self):
        self.name = "error_recovery_agent"  # 添加name属性
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [analyze_error_pattern, generate_recovery_strategy]
        # 已移除 auto_fix_sql_error - 修复成功率过低，建议重新生成 SQL
        
        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业的错误恢复专家。你的任务是：

1. 分析错误模式，识别重复错误和根本原因
2. 制定针对性的恢复策略
3. 提供人工干预建议

恢复流程：
1. 使用 analyze_error_pattern 分析错误历史
2. 使用 generate_recovery_strategy 制定恢复策略

恢复原则：
- 分析错误原因后建议重新生成 SQL
- 识别和避免重复错误
- 提供清晰的恢复步骤
- 评估恢复成功率

你需要智能地分析错误并提供最佳的恢复方案。"""

    async def recover(self, state: SQLMessageState) -> Dict[str, Any]:
        """执行错误恢复"""
        try:
            error_history = state.get("error_history", [])
            current_sql = state.get("generated_sql", "")
            schema_info = state.get("schema_info")
            
            # 获取最新错误
            latest_error = error_history[-1] if error_history else {}
            
            # 准备输入消息
            messages = [
                HumanMessage(content=f"""
请分析以下错误并制定恢复策略：

错误历史: {error_history}
当前SQL: {current_sql}
最新错误: {latest_error}

请分析错误模式、制定恢复策略并尝试自动修复。
""")
            ]
            
            # 调用恢复代理
            result = await self.agent.ainvoke({
                "messages": messages
            })
            
            # 解析恢复结果
            recovery_result = self._parse_recovery_result(result, state)
            
            # 更新状态
            if recovery_result.get("recovery_successful"):
                # 恢复成功，重置错误计数并继续流程
                state["retry_count"] = 0
                state["current_stage"] = recovery_result.get("next_stage", "sql_generation")
                
                # 如果有修复的SQL，更新它
                if recovery_result.get("fixed_sql"):
                    state["generated_sql"] = recovery_result["fixed_sql"]
            else:
                # 恢复失败，增加重试计数
                state["retry_count"] = state.get("retry_count", 0) + 1
                
                if state["retry_count"] >= state.get("max_retries", 3):
                    state["current_stage"] = "terminated"
                else:
                    state["current_stage"] = "error_recovery"
            
            return recovery_result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "recovery_successful": False
            }
    
    def _parse_recovery_result(self, result: Dict[str, Any], state: SQLMessageState) -> Dict[str, Any]:
        """解析恢复结果"""
        messages = result.get("messages", [])
        
        # 默认恢复结果
        recovery_result = {
            "success": True,
            "recovery_successful": False,
            "fixed_sql": None,
            "recovery_strategy": "unknown",
            "next_stage": "sql_generation",
            "recovery_messages": messages
        }
        
        # 简单的结果解析
        for message in messages:
            if hasattr(message, 'content'):
                content = message.content.lower()
                
                if "修复成功" in content or "fixed successfully" in content:
                    recovery_result["recovery_successful"] = True
                
                if "select" in content and "from" in content:
                    # 尝试提取修复的SQL
                    lines = message.content.split('\n')
                    for line in lines:
                        if line.strip().upper().startswith('SELECT'):
                            recovery_result["fixed_sql"] = line.strip()
                            break
        
        return recovery_result


# 创建全局实例
error_recovery_agent = ErrorRecoveryAgent()
