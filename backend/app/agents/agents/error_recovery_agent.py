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

修复历史:
- 2026-01-22: 改进错误消息，提供用户友好的反馈
"""
from typing import Dict, Any, List
import json
import logging
import time

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

logger = logging.getLogger(__name__)


# ============================================================================
# 用户友好的错误消息映射
# ============================================================================

USER_FRIENDLY_MESSAGES = {
    "regenerate_sql": {
        "retrying": "抱歉，生成的查询语句有误。正在为您重新生成更准确的查询...",
        "failed": "很抱歉，多次尝试后仍无法生成正确的查询语句。建议您：\n1. 尝试简化查询描述\n2. 提供更具体的筛选条件\n3. 检查是否涉及不存在的数据"
    },
    "mysql_limit_fix": {
        "retrying": "检测到 MySQL 子查询限制问题，正在使用 JOIN 方式重新生成查询...",
        "failed": "很抱歉，无法自动修复子查询问题。建议您简化查询，分步获取数据。"
    },
    "verify_schema": {
        "retrying": "抱歉，无法找到您查询的数据表或字段。正在重新分析数据库结构...",
        "failed": "很抱歉，无法匹配到相关的数据表。可能原因：\n1. 数据库中没有相关数据\n2. 表名或字段名表述不同\n3. 建议检查数据库连接是否正确"
    },
    "check_connection": {
        "retrying": "数据库连接出现问题，正在尝试重新连接...",
        "failed": "数据库连接失败。请检查：\n1. 网络连接是否正常\n2. 数据库服务是否运行\n3. 连接配置是否正确"
    },
    "simplify_query": {
        "retrying": "当前权限可能不足，正在尝试简化查询...",
        "failed": "权限不足，无法执行此查询。建议：\n1. 联系管理员获取相应权限\n2. 尝试查询其他可访问的数据"
    },
    "optimize_query": {
        "retrying": "查询超时，正在优化查询语句以提高效率...",
        "failed": "查询执行超时。建议：\n1. 缩小查询的时间范围\n2. 减少查询的数据量\n3. 添加更多筛选条件"
    },
    "restart": {
        "retrying": "遇到问题，正在重新开始处理您的查询...",
        "failed": "处理过程中遇到未知问题。建议：\n1. 重新描述您的查询需求\n2. 稍后再试\n3. 如问题持续，请联系技术支持"
    }
}

# 错误类型到动作的映射 (用于获取用户友好消息)
ERROR_TYPE_TO_ACTION = {
    "mysql_limit_subquery_error": "mysql_limit_fix",  # MySQL LIMIT in subquery 特殊处理
    "sql_syntax_error": "regenerate_sql",
    "syntax_error": "regenerate_sql",
    "not_found_error": "verify_schema",
    "connection_error": "check_connection",
    "permission_error": "simplify_query",
    "timeout_error": "optimize_query",
    "unknown_error": "regenerate_sql"  # 未知错误也尝试重新生成
}


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
            
            # 分类错误类型 - 改进的错误识别逻辑
            error_type = _classify_error_type(error_msg)
            
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


def _classify_error_type(error_msg: str) -> str:
    """
    分类错误类型 - 改进的错误识别逻辑
    
    支持识别更多 SQL 相关错误类型:
    - SQL 语法错误 (syntax error)
    - 列/表不存在 (unknown column/table, not found)
    - 连接错误 (connection error)
    - 权限错误 (permission denied)
    - 超时错误 (timeout)
    - 子查询错误 (subquery error)
    - MySQL 特定限制错误 (LIMIT in subquery)
    
    Args:
        error_msg: 小写的错误消息
        
    Returns:
        str: 错误类型标识
    """
    # 1. MySQL 特定限制错误 - 优先检测（这是最常见的复杂查询错误）
    mysql_limit_patterns = [
        "doesn't yet support",
        "limit & in/all/any/some subquery",
        "1235",  # MySQL 错误码
    ]
    
    for pattern in mysql_limit_patterns:
        if pattern in error_msg:
            return "mysql_limit_subquery_error"
    
    # 2. SQL 语法和结构错误 - 最常见，优先检测
    sql_syntax_patterns = [
        "syntax", "语法",
        "unknown column", "unknown table",  # MySQL 特有
        "column .* does not exist",  # PostgreSQL
        "table .* doesn't exist", "table .* not found",
        "no such column", "no such table",  # SQLite
        "invalid identifier",  # Oracle
        "ambiguous column",  # 多表查询中的列名歧义
        "subquery", "子查询",
        "operationalerror", "1054",  # MySQL 错误码 1054 = Unknown column
        "1146",  # MySQL 错误码 1146 = Table doesn't exist
        "42s22", "42s02",  # SQL 状态码
        "in 'where clause'", "in 'field list'", "in 'on clause'",  # MySQL 错误位置提示
        "group by", "having",  # 聚合查询错误
        "1055",  # MySQL ONLY_FULL_GROUP_BY 错误
        "1242",  # Subquery returns more than 1 row
    ]
    
    for pattern in sql_syntax_patterns:
        if pattern in error_msg:
            return "sql_syntax_error"
    
    # 3. 资源不存在错误
    not_found_patterns = [
        "not found", "找不到", "不存在",
        "does not exist", "doesn't exist",
        "no data", "empty result"
    ]
    
    for pattern in not_found_patterns:
        if pattern in error_msg:
            return "not_found_error"
    
    # 4. 连接错误
    connection_patterns = [
        "connection", "连接",
        "refused", "timed out", "unreachable",
        "host", "network", "socket"
    ]
    
    for pattern in connection_patterns:
        if pattern in error_msg:
            return "connection_error"
    
    # 5. 权限错误
    permission_patterns = [
        "permission", "权限", "denied",
        "access denied", "unauthorized",
        "privilege", "forbidden"
    ]
    
    for pattern in permission_patterns:
        if pattern in error_msg:
            return "permission_error"
    
    # 6. 超时错误
    timeout_patterns = [
        "timeout", "超时", "timed out",
        "too long", "slow query"
    ]
    
    for pattern in timeout_patterns:
        if pattern in error_msg:
            return "timeout_error"
    
    # 默认：未知错误
    return "unknown_error"


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
            # MySQL LIMIT in subquery 错误 - 需要特殊处理
            "mysql_limit_subquery_error": {
                "primary_action": "regenerate_sql",
                "description": "MySQL 不支持在 IN/ALL/ANY/SOME 子查询中使用 LIMIT，需要改用 JOIN 派生表",
                "auto_fixable": True,
                "confidence": 0.9,  # 高置信度，因为修复方案明确
                "steps": [
                    "识别使用了 IN + LIMIT 的子查询",
                    "将 WHERE id IN (SELECT ... LIMIT N) 改写为 JOIN 派生表",
                    "正确写法: JOIN (SELECT ... LIMIT N) AS subq ON main.id = subq.id",
                    "确保派生表有别名"
                ],
                "fix_hint": "查询执行失败，错误信息显示MySQL版本不支持在IN子查询中使用LIMIT。我需要修改SQL查询语句，使用JOIN替代IN子查询。"
            },
            # SQL 语法/结构错误 - 可自动修复
            "sql_syntax_error": {
                "primary_action": "regenerate_sql",
                "description": "SQL 语法或结构错误（列名/表名错误、子查询问题等），需要重新生成",
                "auto_fixable": True,
                "confidence": 0.85,
                "steps": [
                    "分析错误原因（列名、表名、子查询结构）",
                    "重新检查 schema 中的正确列名和表名",
                    "使用更简单的 SQL 结构避免子查询问题",
                    "重新生成符合数据库约束的 SQL"
                ]
            },
            # 兼容旧的 syntax_error 类型
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
            },
            # 未知错误 - 改为可尝试自动修复（首次）
            "unknown_error": {
                "primary_action": "regenerate_sql",
                "description": "未知错误，尝试重新生成 SQL",
                "auto_fixable": True,  # 改为 True，允许首次尝试自动修复
                "confidence": 0.5,
                "steps": [
                    "分析错误信息",
                    "简化查询逻辑",
                    "重新生成 SQL"
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
1. 使用 analyze_error_pattern 工具分析错误历史，识别错误类型和模式
2. 使用 generate_recovery_strategy 工具制定恢复策略
3. 只返回恢复方案，不重复错误详情

**错误类型识别**:
- sql_syntax_error: SQL 语法错误、列名/表名不存在
- mysql_limit_subquery_error: MySQL 子查询中使用 LIMIT 的限制
- connection_error: 数据库连接问题
- permission_error: 权限不足
- timeout_error: 查询超时
- not_found_error: 数据不存在

**恢复策略**:
- sql_syntax_error -> 重新生成 SQL，使用正确的列名
- mysql_limit_subquery_error -> 改用 JOIN 派生表方式
- connection_error -> 检查连接配置
- timeout_error -> 优化查询，添加 LIMIT

**禁止的行为**:
- 不要重复输出错误堆栈
- 不要生成冗长的错误分析
- 不要重复调用工具

**输出格式**: 简洁的恢复方案和建议"""
    
    def _get_user_friendly_message(self, action: str, is_retrying: bool) -> str:
        """
        获取用户友好的错误消息
        
        Args:
            action: 恢复动作类型
            is_retrying: 是否正在重试
            
        Returns:
            用户友好的消息文本
        """
        messages = USER_FRIENDLY_MESSAGES.get(action, USER_FRIENDLY_MESSAGES["restart"])
        return messages["retrying"] if is_retrying else messages["failed"]
    
    def _build_enhanced_error_context(
        self,
        error_analysis_data: Dict[str, Any],
        latest_error: Dict[str, Any],
        failed_sql: str,
        primary_action: str,
        recovery_steps: List[str],
        retry_count: int,
        existing_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建增强的错误恢复上下文
        
        关键修复：正确传递列名白名单信息，帮助 LLM 避免幻觉
        
        Args:
            error_analysis_data: 错误分析结果
            latest_error: 最近的错误信息
            failed_sql: 失败的 SQL
            primary_action: 主要恢复动作
            recovery_steps: 恢复步骤
            retry_count: 当前重试次数
            existing_context: 已有的错误上下文（可能包含列名信息）
            
        Returns:
            增强的错误上下文
        """
        error_type = error_analysis_data.get("most_common_type", "unknown")
        error_message = latest_error.get("error", "")
        
        # 基础错误上下文
        error_context = {
            "error_type": error_type,
            "error_message": error_message,
            "failed_sql": failed_sql,
            "recovery_action": primary_action,
            "recovery_steps": recovery_steps,
            "retry_count": retry_count
        }
        
        # ✅ 关键修复：从已有上下文中继承列名信息
        # 这些信息是 sql_generator_agent 在列名验证失败时传递的
        if existing_context:
            # 继承可用列提示
            if existing_context.get("available_columns_hint"):
                error_context["available_columns_hint"] = existing_context["available_columns_hint"]
                logger.info(f"[错误恢复] 继承 available_columns_hint")
            
            # 继承列名白名单
            if existing_context.get("column_whitelist"):
                error_context["column_whitelist"] = existing_context["column_whitelist"]
                logger.info(f"[错误恢复] 继承 column_whitelist: {len(existing_context['column_whitelist'])} 个表")
            
            # 继承修复提示
            if existing_context.get("fix_prompt"):
                error_context["fix_prompt"] = existing_context["fix_prompt"]
                logger.info(f"[错误恢复] 继承 fix_prompt")
            
            # 继承完整表列表
            if existing_context.get("full_table_list"):
                error_context["full_table_list"] = existing_context["full_table_list"]
        
        # ✅ 从 error_history 中提取列名信息（如果存在）
        column_errors = latest_error.get("column_errors", [])
        if column_errors and not error_context.get("available_columns_hint"):
            # 尝试从 error_history 中获取列名白名单
            column_whitelist = latest_error.get("column_whitelist", {})
            if column_whitelist:
                error_context["column_whitelist"] = column_whitelist
                # 构建可用列提示
                available_columns_info = []
                for table_name, cols in column_whitelist.items():
                    available_columns_info.append(f"表 `{table_name}` 的可用列: {', '.join(cols)}")
                error_context["available_columns_hint"] = "\n".join(available_columns_info)
                logger.info(f"[错误恢复] 从 error_history 提取列名白名单: {len(column_whitelist)} 个表")
        
        # ✅ 如果有列名验证错误，构建详细的修复提示
        if column_errors or error_type == "column_validation_failed":
            if not error_context.get("fix_prompt") and error_context.get("available_columns_hint"):
                error_context["fix_prompt"] = f"""
【严重错误】上一次生成的 SQL 使用了不存在的列名！

错误详情:
{chr(10).join(f"  - {err}" for err in column_errors) if column_errors else f"  - {error_message}"}

【正确的列名信息 - 请严格使用以下列名】
{error_context["available_columns_hint"]}

【修复要求】
1. 仔细检查上面的可用列名列表
2. 只使用列表中存在的列名
3. 不要猜测或虚构任何列名
4. 如果需要计算某个指标（如库存总量），请使用实际存在的列进行计算
   例如：使用 SUM(quantity) 而不是 total_inventory

请重新生成 SQL，确保所有列名都在可用列表中。
"""
                logger.info(f"[错误恢复] 构建了详细的 fix_prompt")
        
        return error_context
    
    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        执行错误恢复
        
        修复 (2026-01-22): 改进错误消息，提供用户友好的反馈
        修复 (2026-01-23): 将错误上下文传递给下一阶段，支持智能重试
        修复 (2026-01-28): 正确传递列名白名单信息，解决 LLM 幻觉问题
        """
        try:
            error_history = state.get("error_history", [])
            current_stage = state.get("current_stage", "init")
            retry_count = state.get("retry_count", 0)
            max_retries = state.get("max_retries", 3)
            failed_sql = state.get("generated_sql", "")  # 获取失败的 SQL
            
            # ✅ 关键修复：从 state 中获取已有的 error_recovery_context
            # 这个上下文可能包含 sql_generator_agent 传递的详细列名信息
            existing_error_context = state.get("error_recovery_context", {})
            
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
            error_analysis_data = json.loads(error_analysis)
            
            # 决定下一步
            if strategy_data.get("success"):
                strategy_info = strategy_data.get("strategy", {})
                primary_action = strategy_info.get("primary_action", "regenerate_sql")
                
                if strategy_info.get("auto_fixable") and retry_count < max_retries:
                    # 可以自动修复，返回到适当的阶段重试
                    if primary_action in ["regenerate_sql", "optimize_query"]:
                        next_stage = "sql_generation"
                    elif primary_action == "verify_schema":
                        next_stage = "schema_analysis"
                    else:
                        next_stage = "sql_generation"  # 默认尝试重新生成 SQL
                    
                    # 获取用户友好的消息
                    user_message = self._get_user_friendly_message(primary_action, is_retrying=True)
                    
                    # 提取最近的错误信息用于重试上下文
                    latest_error = error_history[-1] if error_history else {}
                    
                    # ✅ 关键修复：构建增强的错误上下文，包含列名白名单信息
                    next_retry_count = retry_count + 1 if current_stage != "error_recovery" else retry_count
                    error_context = self._build_enhanced_error_context(
                        error_analysis_data=error_analysis_data,
                        latest_error=latest_error,
                        failed_sql=failed_sql or existing_error_context.get("failed_sql", ""),
                        primary_action=primary_action,
                        recovery_steps=strategy_info.get("steps", []),
                        retry_count=next_retry_count,
                        existing_context=existing_error_context
                    )
                    
                    logger.info(f"错误恢复: {primary_action} -> {next_stage} (重试 {next_retry_count}/{max_retries})")
                    logger.info(f"错误类型: {error_context['error_type']}, 失败SQL长度: {len(error_context.get('failed_sql', ''))}")
                    logger.info(f"是否包含列名提示: {bool(error_context.get('available_columns_hint'))}")
                    
                    # ✅ 修复：发送流式事件通知前端正在重试
                    try:
                        from langgraph.config import get_stream_writer
                        from app.schemas.stream_events import create_node_event
                        
                        writer = get_stream_writer()
                        if writer:
                            # 发送错误恢复状态事件
                            writer(create_node_event(
                                node="error_recovery",
                                status="retrying",
                                message=user_message,
                                metadata={
                                    "retry_count": next_retry_count,
                                    "max_retries": max_retries,
                                    "error_type": error_context["error_type"],
                                    "next_stage": next_stage
                                }
                            ))
                    except Exception as e:
                        logger.debug(f"发送流式事件失败（非关键）: {e}")
                    
                    return {
                        "messages": [AIMessage(content=user_message)],
                        "current_stage": next_stage,
                        "retry_count": next_retry_count,
                        "error_recovery_context": error_context,  # 传递增强的错误上下文给下一阶段
                        "generated_sql": None  # 清除失败的 SQL，强制重新生成
                    }
                else:
                    # 无法自动修复或已达到重试限制
                    user_message = self._get_user_friendly_message(primary_action, is_retrying=False)
                    
                    # 如果达到重试限制，添加额外说明
                    if retry_count >= max_retries:
                        user_message = f"已尝试 {retry_count} 次仍未成功。\n\n{user_message}"
                    
                    logger.warning(f"错误恢复失败: {primary_action}, 重试次数: {retry_count}")
                    
                    return {
                        "messages": [AIMessage(content=user_message)],
                        "current_stage": "completed" if retry_count >= max_retries else "error_recovery",
                        "retry_count": retry_count,  # 保持当前重试次数
                        "error_history": error_history + [{
                            "stage": "error_recovery",
                            "error": f"恢复失败: {primary_action}",
                            "retry_count": retry_count,
                            "timestamp": time.time()
                        }]
                    }
            else:
                # 错误分析失败，但仍尝试一次自动修复
                if retry_count < max_retries:
                    logger.warning(f"错误分析失败，但仍尝试重新生成 SQL (重试 {retry_count}/{max_retries})")
                    
                    return {
                        "messages": [AIMessage(content="正在重新尝试生成查询...")],
                        "current_stage": "sql_generation",
                        "retry_count": retry_count,  # ✅ 修复：不再递增，因为已在 sql_generator_agent 中递增
                        "error_recovery_context": {
                            "error_type": "unknown",
                            "error_message": str(error_history[-1].get("error", "") if error_history else ""),
                            "failed_sql": failed_sql,
                            "recovery_action": "regenerate_sql",
                            "retry_count": retry_count
                        },
                        "generated_sql": None
                    }
                
                user_message = "抱歉，处理过程中遇到问题。请尝试重新描述您的查询需求。"
                logger.error(f"错误分析失败: {strategy_data.get('error')}")
                
                return {
                    "messages": [AIMessage(content=user_message)],
                    "current_stage": "error_recovery",  # ✅ 保持 error_recovery 状态
                    "retry_count": retry_count
                }
            
        except Exception as e:
            logger.error(f"错误恢复异常: {str(e)}")
            
            # 即使异常也尝试一次恢复
            retry_count = state.get("retry_count", 0)
            max_retries = state.get("max_retries", 3)
            
            if retry_count < max_retries:
                logger.warning(f"错误恢复异常，但仍尝试重新生成 SQL (重试 {retry_count}/{max_retries})")
                return {
                    "messages": [AIMessage(content="正在重新尝试生成查询...")],
                    "current_stage": "sql_generation",
                    "retry_count": retry_count,  # ✅ 修复：不再递增
                    "generated_sql": None
                }
            
            user_message = "抱歉，处理过程中遇到未知问题。请稍后再试，如问题持续请联系技术支持。"
            
            return {
                "messages": [AIMessage(content=user_message)],
                "current_stage": "error_recovery",  # ✅ 保持 error_recovery 状态
                "retry_count": state.get("retry_count", 0),
                "error_history": state.get("error_history", []) + [{
                    "stage": "error_recovery",
                    "error": str(e),
                    "retry_count": state.get("retry_count", 0),
                    "timestamp": time.time()
                }]
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
