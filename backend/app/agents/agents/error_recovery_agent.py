"""
错误恢复代理 (优化版本)

遵循 LangGraph 官方最佳实践:
1. 使用标准 JSON 格式返回
2. 简化错误分析和恢复策略
3. 与其他 Agent 保持一致的接口

核心职责:
- 分析错误模式
- 提供恢复策略
- 协助重试决策
"""
from typing import Dict, Any, List
import json
import logging

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

logger = logging.getLogger(__name__)


# ============================================================================
# 错误分析工具
# ============================================================================

@tool
def analyze_error_pattern(error_history: str) -> str:
    """
    分析错误模式，识别重复错误和根本原因
    
    Args:
        error_history: JSON 格式的错误历史记录
        
    Returns:
        str: JSON 格式的错误模式分析结果
    """
    try:
        # 解析输入
        errors = json.loads(error_history) if isinstance(error_history, str) else error_history
        
        if not errors:
            return json.dumps({
                "success": True,
                "pattern_found": False,
                "message": "没有错误历史记录"
            }, ensure_ascii=False)
        
        # 统计错误类型
        error_types = {}
        error_stages = {}
        
        for error in errors:
            error_msg = str(error.get("error", "")).lower()
            stage = error.get("stage", "unknown")
            
            # 分类错误类型
            if "syntax" in error_msg or "语法" in error_msg:
                error_type = "syntax_error"
            elif "connection" in error_msg or "连接" in error_msg:
                error_type = "connection_error"
            elif "permission" in error_msg or "权限" in error_msg:
                error_type = "permission_error"
            elif "timeout" in error_msg or "超时" in error_msg:
                error_type = "timeout_error"
            elif "not found" in error_msg or "找不到" in error_msg:
                error_type = "not_found_error"
            else:
                error_type = "unknown_error"
            
            error_types[error_type] = error_types.get(error_type, 0) + 1
            error_stages[stage] = error_stages.get(stage, 0) + 1
        
        # 识别模式
        most_common_type = max(error_types.items(), key=lambda x: x[1]) if error_types else ("none", 0)
        most_common_stage = max(error_stages.items(), key=lambda x: x[1]) if error_stages else ("none", 0)
        
        pattern_found = most_common_type[1] > 1 or most_common_stage[1] > 1
        
        return json.dumps({
            "success": True,
            "pattern_found": pattern_found,
            "error_types": error_types,
            "error_stages": error_stages,
            "most_common_type": most_common_type[0],
            "most_common_stage": most_common_stage[0],
            "total_errors": len(errors)
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"错误模式分析失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


@tool
def generate_recovery_strategy(
    error_analysis: str,
    retry_count: int = 0
) -> str:
    """
    基于错误分析生成恢复策略
    
    Args:
        error_analysis: JSON 格式的错误分析结果
        retry_count: 当前重试次数
        
    Returns:
        str: JSON 格式的恢复策略建议
    """
    try:
        analysis = json.loads(error_analysis) if isinstance(error_analysis, str) else error_analysis
        
        most_common_type = analysis.get("most_common_type", "unknown")
        
        # 基于错误类型制定策略
        strategies = {
            "syntax_error": {
                "primary_action": "regenerate_sql",
                "description": "SQL 语法错误，建议重新生成",
                "auto_fixable": True,
                "confidence": 0.8,
                "steps": [
                    "重新分析用户查询意图",
                    "使用更严格的 SQL 生成约束",
                    "验证生成的 SQL 语法"
                ]
            },
            "connection_error": {
                "primary_action": "check_connection",
                "description": "数据库连接问题，需要检查连接配置",
                "auto_fixable": False,
                "confidence": 0.6,
                "steps": [
                    "检查数据库连接状态",
                    "验证连接参数",
                    "尝试重新连接"
                ]
            },
            "permission_error": {
                "primary_action": "simplify_query",
                "description": "权限不足，建议简化查询范围",
                "auto_fixable": False,
                "confidence": 0.4,
                "steps": [
                    "减少查询的表数量",
                    "移除敏感字段",
                    "使用更基本的查询"
                ]
            },
            "timeout_error": {
                "primary_action": "optimize_query",
                "description": "查询超时，建议优化查询",
                "auto_fixable": True,
                "confidence": 0.7,
                "steps": [
                    "添加 LIMIT 子句",
                    "优化 JOIN 操作",
                    "减少查询字段"
                ]
            },
            "not_found_error": {
                "primary_action": "verify_schema",
                "description": "表或字段不存在，需要重新分析 schema",
                "auto_fixable": True,
                "confidence": 0.75,
                "steps": [
                    "重新检索数据库 schema",
                    "验证表名和字段名",
                    "使用正确的值映射"
                ]
            }
        }
        
        strategy = strategies.get(most_common_type, {
            "primary_action": "restart",
            "description": "未知错误类型，建议从头开始",
            "auto_fixable": False,
            "confidence": 0.3,
            "steps": ["重新开始整个流程"]
        })
        
        # 根据重试次数调整
        if retry_count >= 2:
            strategy["confidence"] *= 0.5
            strategy["recommendation"] = "已多次重试，建议人工干预"
        
        return json.dumps({
            "success": True,
            "strategy": strategy,
            "estimated_success_rate": strategy["confidence"]
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"恢复策略生成失败: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False)


# ============================================================================
# 错误恢复代理类
# ============================================================================

class ErrorRecoveryAgent:
    """
    错误恢复代理 - 简化版本
    
    职责:
    - 分析错误模式
    - 提供恢复策略
    - 协助决定是否重试
    """
    
    def __init__(self):
        self.name = "error_recovery_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [analyze_error_pattern, generate_recovery_strategy]
        
        # 创建 ReAct 代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业的错误恢复专家。

**核心职责**: 分析错误原因，制定恢复策略

**工作流程**:
1. 使用 analyze_error_pattern 工具分析错误历史
2. 使用 generate_recovery_strategy 工具制定恢复策略
3. **只返回恢复方案，不重复错误详情**

**输出内容**:
- 错误类型和根因
- 具体的恢复步骤
- 预期成功率

**禁止的行为**:
- ❌ 不要重复输出错误堆栈
- ❌ 不要生成冗长的错误分析
- ❌ 不要重复调用工具

**输出格式**: 简洁的恢复方案和建议"""
    
    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """执行错误恢复"""
        try:
            error_history = state.get("error_history", [])
            retry_count = state.get("retry_count", 0)
            
            # 分析错误
            error_analysis = analyze_error_pattern.invoke({
                "error_history": json.dumps(error_history, ensure_ascii=False)
            })
            
            # 生成恢复策略
            strategy = generate_recovery_strategy.invoke({
                "error_analysis": error_analysis,
                "retry_count": retry_count
            })
            
            # 解析策略
            strategy_data = json.loads(strategy)
            
            # 决定下一步
            if strategy_data.get("success"):
                strategy_info = strategy_data.get("strategy", {})
                
                if strategy_info.get("auto_fixable") and retry_count < state.get("max_retries", 3):
                    # 可以自动修复，返回到适当的阶段重试
                    primary_action = strategy_info.get("primary_action", "restart")
                    
                    if primary_action == "regenerate_sql":
                        next_stage = "sql_generation"
                    elif primary_action == "verify_schema":
                        next_stage = "schema_analysis"
                    else:
                        next_stage = "schema_analysis"
                    
                    return {
                        "messages": [AIMessage(content=f"错误恢复: {strategy_info.get('description')}")],
                        "current_stage": next_stage,
                        "retry_count": retry_count + 1
                    }
                else:
                    # 无法自动修复或已达到重试限制
                    return {
                        "messages": [AIMessage(content=f"错误恢复失败: {strategy_info.get('description')}")],
                        "current_stage": "completed"
                    }
            else:
                return {
                    "messages": [AIMessage(content="错误分析失败，终止流程")],
                    "current_stage": "completed"
                }
            
        except Exception as e:
            logger.error(f"错误恢复失败: {str(e)}")
            return {
                "messages": [AIMessage(content=f"错误恢复失败: {str(e)}")],
                "current_stage": "completed"
            }


# ============================================================================
# 节点函数 (用于 LangGraph 图)
# ============================================================================

async def error_recovery_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    错误恢复节点函数 - 用于 LangGraph 图
    """
    agent = ErrorRecoveryAgent()
    return await agent.process(state)


# ============================================================================
# 导出
# ============================================================================

# 创建全局实例（兼容现有代码）
error_recovery_agent = ErrorRecoveryAgent()

__all__ = [
    "error_recovery_agent",
    "error_recovery_node",
    "analyze_error_pattern",
    "generate_recovery_strategy",
    "ErrorRecoveryAgent",
]
