"""
错误恢复代理
负责分析错误、提供恢复策略和自动修复能力
"""
import logging
from typing import Dict, Any, List, Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.types import Command

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

logger = logging.getLogger(__name__)


@tool
def analyze_error_pattern(error_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析错误模式，识别重复错误和根本原因
    
    Args:
        error_history: 错误历史记录
        
    Returns:
        错误模式分析结果
    """
    try:
        if not error_history:
            return {
                "success": True,
                "pattern_found": False,
                "message": "没有错误历史记录"
            }
        
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
        
        return {
            "success": True,
            "pattern_found": pattern_found,
            "error_types": error_types,
            "error_stages": error_stages,
            "most_common_type": most_common_type[0],
            "most_common_stage": most_common_stage[0],
            "total_errors": len(error_history)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@tool
def generate_recovery_strategy(error_analysis: Dict[str, Any], current_state: Dict[str, Any]) -> Dict[str, Any]:
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
        
        return {
            "success": True,
            "strategy": strategy,
            "recovery_steps": recovery_steps,
            "estimated_success_rate": strategy["confidence"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@tool
def auto_fix_sql_error(
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    自动修复SQL错误。从Supervisor状态中获取SQL、错误历史和Schema信息。
    
    Returns:
        Command: 更新 generated_sql 和 current_stage 的命令
    """
    try:
        # 从状态获取必要信息
        sql_query = state.get("generated_sql", "")
        error_history = state.get("error_history", [])
        schema_info = state.get("schema_info", {})
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        
        if not sql_query:
            return Command(
                graph=Command.PARENT,
                update={
                    "current_stage": "terminated",
                    "messages": [ToolMessage(
                        content="恢复失败：没有找到需要修复的 SQL 语句",
                        tool_call_id=tool_call_id
                    )]
                }
            )
        
        # 获取最新错误消息
        error_message = ""
        if error_history:
            latest_error = error_history[-1]
            error_message = latest_error.get("error", "")
        
        fixed_sql = sql_query
        fixes_applied = []
        error_lower = error_message.lower()
        
        # 常见语法错误修复
        if "syntax error" in error_lower or "语法错误" in error_lower:
            if not fixed_sql.strip().endswith(';'):
                fixed_sql += ';'
                fixes_applied.append("添加缺失的分号")
            
            keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'ON', 'GROUP BY', 'ORDER BY', 'HAVING']
            for keyword in keywords:
                fixed_sql = fixed_sql.replace(keyword.lower(), keyword)
            
            if fixed_sql.count("'") % 2 != 0:
                fixed_sql += "'"
                fixes_applied.append("修复未闭合的单引号")
        
        # 表名或字段名错误修复
        if "unknown column" in error_lower or "unknown table" in error_lower:
            schema_context = schema_info.get("schema_context", {})
            if isinstance(schema_context, dict):
                for table in schema_context.keys():
                    if table.lower() in fixed_sql.lower():
                        fixed_sql = fixed_sql.replace(table.lower(), table)
                        fixes_applied.append(f"修正表名为 {table}")
        
        # 性能相关修复
        if "timeout" in error_lower or "too many rows" in error_lower:
            if "LIMIT" not in fixed_sql.upper():
                fixed_sql += " LIMIT 100"
                fixes_applied.append("添加LIMIT子句限制结果数量")
        
        # 权限相关修复
        if "access denied" in error_lower or "permission" in error_lower:
            if "SELECT *" in fixed_sql.upper():
                fixed_sql = fixed_sql.replace("SELECT *", "SELECT id, name")
                fixes_applied.append("简化SELECT字段以避免权限问题")
        
        # 确定结果和下一阶段
        fix_successful = len(fixes_applied) > 0 or fixed_sql != sql_query
        
        if fix_successful:
            next_stage = "sql_validation"  # 修复后重新验证
            message = f"SQL 自动修复完成: {', '.join(fixes_applied) if fixes_applied else '已修复'}"
            new_retry_count = 0
            logger.info(f"[ErrorRecovery] {message}")
        else:
            new_retry_count = retry_count + 1
            if new_retry_count >= max_retries:
                next_stage = "terminated"
                message = f"SQL 自动修复失败，已达最大重试次数 ({max_retries})"
            else:
                next_stage = "sql_generation"  # 重新生成
                message = f"无法自动修复，将重新生成 SQL (重试 {new_retry_count}/{max_retries})"
            logger.warning(f"[ErrorRecovery] {message}")
        
        # 返回 Command 更新父图状态
        update_dict = {
            "current_stage": next_stage,
            "retry_count": new_retry_count,
            "messages": [ToolMessage(content=message, tool_call_id=tool_call_id)]
        }
        
        if fix_successful:
            update_dict["generated_sql"] = fixed_sql
        
        return Command(graph=Command.PARENT, update=update_dict)
        
    except Exception as e:
        logger.error(f"[ErrorRecovery] 修复异常: {e}")
        return Command(
            graph=Command.PARENT,
            update={
                "current_stage": "terminated",
                "messages": [ToolMessage(
                    content=f"SQL 修复失败: {str(e)}",
                    tool_call_id=tool_call_id
                )]
            }
        )


class ErrorRecoveryAgent:
    """错误恢复代理"""

    def __init__(self):
        self.name = "error_recovery_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [analyze_error_pattern, generate_recovery_strategy, auto_fix_sql_error]
        
        # 创建ReAct代理（使用自定义 state_schema 以支持 connection_id 等字段）
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name,
            state_schema=SQLMessageState,
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业的错误恢复专家。你的任务是：

1. 分析错误模式，识别重复错误和根本原因
2. 制定针对性的恢复策略
3. 自动修复可修复的错误
4. 提供人工干预建议

恢复流程：
1. 使用 analyze_error_pattern 分析错误历史
2. 使用 generate_recovery_strategy 制定恢复策略
3. 使用 auto_fix_sql_error 尝试自动修复

恢复原则：
- 优先尝试自动修复
- 识别和避免重复错误
- 提供清晰的恢复步骤
- 评估修复成功率

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
                state["retry_count"] = 0
                state["current_stage"] = recovery_result.get("next_stage", "sql_generation")
                
                state["thought"] = f"分析发现错误原因为：{recovery_result.get('error_reason')}。我已制定了修复策略：{recovery_result.get('recovery_strategy')}。目前修复已完成，准备重新执行。"
                state["next_plan"] = f"重新进入 {state['current_stage']} 阶段。"
                
                from langgraph.config import get_stream_writer
                from app.schemas.stream_events import create_thought_event, create_node_event
                writer = get_stream_writer()
                if writer:
                    writer(create_thought_event(
                        agent="error_recovery_agent",
                        thought=state["thought"],
                        plan=state["next_plan"]
                    ))
                    writer(create_node_event(
                        node="error_recovery_agent",
                        status="completed",
                        message="错误已自动修复"
                    ))
                
                if recovery_result.get("fixed_sql"):
                    state["generated_sql"] = recovery_result["fixed_sql"]
            else:
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
        
        recovery_result = {
            "success": True,
            "recovery_successful": False,
            "fixed_sql": None,
            "recovery_strategy": "unknown",
            "next_stage": "sql_generation",
            "recovery_messages": messages
        }
        
        for message in messages:
            if hasattr(message, 'content'):
                content = message.content.lower()
                
                if "修复成功" in content or "fixed successfully" in content:
                    recovery_result["recovery_successful"] = True
                
                if "select" in content and "from" in content:
                    lines = message.content.split('\n')
                    for line in lines:
                        if line.strip().upper().startswith('SELECT'):
                            recovery_result["fixed_sql"] = line.strip()
                            break
        
        return recovery_result


# 创建全局实例
error_recovery_agent = ErrorRecoveryAgent()
