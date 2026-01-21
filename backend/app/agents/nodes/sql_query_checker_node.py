"""
SQL Query Checker 节点

借鉴 LangGraph 官方 sql_db_query_checker 工具的实现思想。
在 SQL 生成后、执行前进行检查，减少执行错误。

核心功能:
1. 语法检查: 检查 SQL 语法是否正确
2. 语义检查: 检查表名、字段名是否存在
3. 安全检查: 检查是否包含危险操作
4. 性能检查: 检查是否有潜在的性能问题

工作流程:
1. 接收生成的 SQL 和 schema 信息
2. 使用 LLM 进行智能检查
3. 返回检查结果和修复建议
4. 如果检查失败，可以自动修复

参考:
https://docs.langchain.com/oss/python/langgraph/sql-agent
"""
from typing import Dict, Any, Optional, List
import logging
import re

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR

# 配置日志
logger = logging.getLogger(__name__)


# ============================================================================
# SQL Query Checker 工具 (参考官方 sql_db_query_checker)
# ============================================================================

@tool
def check_sql_query(
    sql_query: str,
    db_type: str = "mysql",
    schema_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    检查 SQL 查询的正确性 - 参考官方 sql_db_query_checker
    
    Use this tool to double check if your query is correct before executing it.
    Always use this tool before executing a query with sql_db_query!
    
    Args:
        sql_query: 要检查的 SQL 查询
        db_type: 数据库类型 (mysql, postgresql, sqlite)
        schema_info: 可选的 schema 信息，用于验证表名和字段名
        
    Returns:
        检查结果，包含:
        - is_valid: 是否有效
        - errors: 错误列表
        - warnings: 警告列表
        - fixed_sql: 修复后的 SQL（如果有修复）
        - suggestions: 改进建议
    """
    try:
        errors = []
        warnings = []
        suggestions = []
        fixed_sql = sql_query.strip()
        
        # ============================================
        # 1. 基本语法检查 (规则驱动，快速)
        # ============================================
        
        sql_upper = fixed_sql.upper()
        
        # 1.1 检查是否是完整的 SQL 语句
        if not any(sql_upper.startswith(kw) for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH']):
            errors.append("SQL 语句不完整，应以 SELECT/INSERT/UPDATE/DELETE/WITH 开头")
        
        # 1.2 检查 SELECT 语句必须有 FROM（除非是常量查询）
        if sql_upper.startswith('SELECT') and 'FROM' not in sql_upper:
            if 'SELECT 1' not in sql_upper and 'SELECT NOW()' not in sql_upper:
                warnings.append("SELECT 语句缺少 FROM 子句")
        
        # 1.3 检查引号匹配
        single_quotes = fixed_sql.count("'")
        if single_quotes % 2 != 0:
            errors.append("单引号未闭合")
            # 尝试修复
            fixed_sql = fixed_sql + "'"
            suggestions.append("已尝试闭合单引号")
        
        double_quotes = fixed_sql.count('"')
        if double_quotes % 2 != 0:
            errors.append("双引号未闭合")
            fixed_sql = fixed_sql + '"'
            suggestions.append("已尝试闭合双引号")
        
        # 1.4 检查括号匹配
        open_parens = fixed_sql.count('(')
        close_parens = fixed_sql.count(')')
        if open_parens != close_parens:
            errors.append(f"括号不匹配: 左括号 {open_parens} 个，右括号 {close_parens} 个")
        
        # ============================================
        # 2. 安全检查 (关键)
        # ============================================
        
        # 2.1 检查危险操作
        dangerous_keywords = ['DROP', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE']
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', sql_upper):
                errors.append(f"检测到危险操作: {keyword}")
        
        # 2.2 检查 DELETE/UPDATE 是否有 WHERE 子句
        if sql_upper.startswith('DELETE') and 'WHERE' not in sql_upper:
            errors.append("DELETE 语句缺少 WHERE 子句，可能会删除所有数据")
        
        if sql_upper.startswith('UPDATE') and 'WHERE' not in sql_upper:
            errors.append("UPDATE 语句缺少 WHERE 子句，可能会更新所有数据")
        
        # 2.3 检查 SQL 注入风险
        injection_patterns = [
            r';\s*--',  # 注释注入
            r';\s*(DROP|DELETE|UPDATE|INSERT)',  # 多语句注入
            r"'\s*OR\s+1\s*=\s*1",  # 经典注入
            r"UNION\s+SELECT\s+.*\s+FROM\s+information_schema",  # 信息泄露
        ]
        for pattern in injection_patterns:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                errors.append(f"检测到潜在 SQL 注入风险: {pattern[:30]}...")
        
        # ============================================
        # 3. 性能检查
        # ============================================
        
        # 3.1 检查 SELECT *
        if 'SELECT *' in sql_upper or 'SELECT\t*' in sql_upper or 'SELECT\n*' in sql_upper:
            warnings.append("使用 SELECT * 可能影响性能，建议指定具体字段")
        
        # 3.2 检查是否有 LIMIT
        if sql_upper.startswith('SELECT') and 'LIMIT' not in sql_upper:
            if 'COUNT(' not in sql_upper and 'SUM(' not in sql_upper and 'AVG(' not in sql_upper:
                warnings.append("SELECT 查询缺少 LIMIT 子句，可能返回大量数据")
                suggestions.append("建议添加 LIMIT 子句限制结果数量")
        
        # 3.3 检查 LIKE 的前缀通配符
        if re.search(r"LIKE\s+['\"]%", fixed_sql, re.IGNORECASE):
            warnings.append("LIKE 使用前缀通配符 '%xxx' 无法使用索引，可能导致全表扫描")
        
        # ============================================
        # 4. Schema 验证 (如果提供了 schema_info)
        # ============================================
        
        if schema_info:
            # 提取 SQL 中的表名
            table_pattern = r'(?:FROM|JOIN|INTO|UPDATE)\s+[`"\[]?(\w+)[`"\]]?'
            tables_in_sql = re.findall(table_pattern, sql_upper, re.IGNORECASE)
            
            # 获取可用的表名
            available_tables = []
            if isinstance(schema_info, dict):
                if 'tables' in schema_info:
                    available_tables = [t.get('name', '').upper() for t in schema_info.get('tables', [])]
                else:
                    available_tables = [k.upper() for k in schema_info.keys()]
            
            # 检查表是否存在
            for table in tables_in_sql:
                if table.upper() not in available_tables and available_tables:
                    warnings.append(f"表 '{table}' 可能不存在，请检查表名是否正确")
        
        # ============================================
        # 5. 确保 SQL 以分号结尾
        # ============================================
        
        if not fixed_sql.endswith(';'):
            fixed_sql = fixed_sql + ';'
        
        # ============================================
        # 6. 生成检查结果
        # ============================================
        
        is_valid = len(errors) == 0
        
        return {
            "success": True,
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "fixed_sql": fixed_sql if fixed_sql != sql_query else None,
            "original_sql": sql_query
        }
        
    except Exception as e:
        logger.error(f"SQL 检查失败: {e}")
        return {
            "success": False,
            "is_valid": False,
            "errors": [str(e)],
            "warnings": [],
            "suggestions": [],
            "fixed_sql": None,
            "original_sql": sql_query
        }


@tool
def check_sql_with_llm(
    sql_query: str,
    user_query: str,
    schema_info: Optional[Dict[str, Any]] = None,
    db_type: str = "mysql"
) -> Dict[str, Any]:
    """
    使用 LLM 智能检查 SQL 查询 - 增强版 query_checker
    
    除了基本语法检查外，还使用 LLM 进行语义检查：
    - SQL 是否准确回答了用户问题
    - 是否有更优的查询方式
    - 是否遗漏了重要条件
    
    Args:
        sql_query: 要检查的 SQL 查询
        user_query: 用户原始查询
        schema_info: schema 信息
        db_type: 数据库类型
        
    Returns:
        检查结果
    """
    try:
        # 先进行基本检查
        basic_check = check_sql_query.invoke({
            "sql_query": sql_query,
            "db_type": db_type,
            "schema_info": schema_info
        })
        
        # 如果基本检查有严重错误，直接返回
        if basic_check.get("errors"):
            return basic_check
        
        # 使用 LLM 进行语义检查
        llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        
        prompt = f"""请检查以下 SQL 查询是否正确回答了用户的问题。

用户问题: {user_query}

生成的 SQL:
```sql
{sql_query}
```

数据库类型: {db_type}

Schema 信息:
{schema_info if schema_info else '未提供'}

请检查以下几点:
1. SQL 语法是否正确
2. SQL 是否准确回答了用户的问题
3. 是否有遗漏的过滤条件
4. 是否有更优的查询方式

请以 JSON 格式返回检查结果:
{{
    "is_correct": true/false,
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"],
    "improved_sql": "改进后的SQL（如果需要）"
}}

如果 SQL 完全正确，返回:
{{
    "is_correct": true,
    "issues": [],
    "suggestions": [],
    "improved_sql": null
}}
"""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # 解析 LLM 响应
        import json
        try:
            # 尝试从响应中提取 JSON
            content = response.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                llm_result = json.loads(json_match.group())
            else:
                llm_result = {"is_correct": True, "issues": [], "suggestions": []}
        except json.JSONDecodeError:
            llm_result = {"is_correct": True, "issues": [], "suggestions": []}
        
        # 合并检查结果
        is_valid = basic_check["is_valid"] and llm_result.get("is_correct", True)
        
        all_errors = basic_check.get("errors", []) + llm_result.get("issues", [])
        all_warnings = basic_check.get("warnings", [])
        all_suggestions = basic_check.get("suggestions", []) + llm_result.get("suggestions", [])
        
        fixed_sql = llm_result.get("improved_sql") or basic_check.get("fixed_sql")
        
        return {
            "success": True,
            "is_valid": is_valid,
            "errors": all_errors,
            "warnings": all_warnings,
            "suggestions": all_suggestions,
            "fixed_sql": fixed_sql,
            "original_sql": sql_query,
            "llm_checked": True
        }
        
    except Exception as e:
        logger.error(f"LLM SQL 检查失败: {e}")
        # 降级到基本检查
        return check_sql_query.invoke({
            "sql_query": sql_query,
            "db_type": db_type,
            "schema_info": schema_info
        })


# ============================================================================
# SQL Query Checker 节点
# ============================================================================

async def sql_query_checker_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    SQL Query Checker 节点 - LangGraph 节点函数
    
    借鉴官方 sql_db_query_checker 的设计思想：
    Use this tool to double check if your query is correct before executing it.
    
    该节点在 SQL 生成后、执行前运行：
    1. 快速模式：仅进行规则检查
    2. 完整模式：规则检查 + LLM 语义检查
    
    Args:
        state: 当前的 SQL 消息状态
        
    Returns:
        Dict[str, Any]: 状态更新
            - sql_check_passed: 检查是否通过
            - generated_sql: 可能修复后的 SQL
            - current_stage: 下一阶段
    """
    logger.info("=== SQL Query Checker 节点 ===")
    
    # 1. 获取必要信息
    generated_sql = state.get("generated_sql")
    
    if not generated_sql:
        logger.warning("没有找到生成的 SQL，跳过检查")
        return {
            "sql_check_passed": False,
            "current_stage": "error_recovery"
        }
    
    # 检查是否启用 query_checker
    enable_query_checker = state.get("enable_query_checker", True)
    if not enable_query_checker:
        logger.info("Query Checker 已禁用，跳过检查")
        return {
            "sql_check_passed": True,
            "current_stage": "sql_execution"
        }
    
    # 2. 获取上下文信息
    schema_info = state.get("schema_info")
    fast_mode = state.get("fast_mode", False)
    
    # 提取用户查询
    messages = state.get("messages", [])
    user_query = None
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            user_query = msg.content
            if isinstance(user_query, list):
                user_query = user_query[0].get("text", "") if user_query else ""
            break
    
    logger.info(f"检查 SQL: {generated_sql[:100]}...")
    logger.info(f"模式: {'快速' if fast_mode else '完整'}")
    
    # 3. 执行检查
    try:
        if fast_mode:
            # 快速模式：仅规则检查
            check_result = check_sql_query.invoke({
                "sql_query": generated_sql,
                "db_type": "mysql",
                "schema_info": schema_info
            })
        else:
            # 完整模式：规则检查 + LLM 检查
            check_result = check_sql_with_llm.invoke({
                "sql_query": generated_sql,
                "user_query": user_query or "",
                "schema_info": schema_info,
                "db_type": "mysql"
            })
        
        is_valid = check_result.get("is_valid", False)
        errors = check_result.get("errors", [])
        warnings = check_result.get("warnings", [])
        fixed_sql = check_result.get("fixed_sql")
        
        logger.info(f"检查结果: valid={is_valid}, errors={len(errors)}, warnings={len(warnings)}")
        
        # 4. 处理检查结果
        if is_valid or (not errors and warnings):
            # 检查通过（可能有警告）
            final_sql = fixed_sql or generated_sql
            
            if warnings:
                logger.warning(f"SQL 检查警告: {warnings}")
            
            return {
                "sql_check_passed": True,
                "generated_sql": final_sql,
                "current_stage": "sql_execution"
            }
        else:
            # 检查失败
            logger.error(f"SQL 检查失败: {errors}")
            
            if fixed_sql:
                # 有修复建议，使用修复后的 SQL
                logger.info(f"使用修复后的 SQL: {fixed_sql[:100]}...")
                return {
                    "sql_check_passed": True,
                    "generated_sql": fixed_sql,
                    "current_stage": "sql_execution"
                }
            else:
                # 无法自动修复，进入错误恢复
                error_info = {
                    "stage": "sql_check",
                    "error": "; ".join(errors),
                    "sql_query": generated_sql,
                    "retry_count": state.get("retry_count", 0)
                }
                
                error_history = state.get("error_history", [])
                error_history.append(error_info)
                
                return {
                    "sql_check_passed": False,
                    "error_history": error_history,
                    "current_stage": "error_recovery"
                }
                
    except Exception as e:
        logger.error(f"SQL 检查异常: {e}", exc_info=True)
        # 检查失败，但仍继续执行（降级处理）
        return {
            "sql_check_passed": True,  # 降级：允许继续执行
            "current_stage": "sql_execution"
        }


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "check_sql_query",
    "check_sql_with_llm",
    "sql_query_checker_node",
]
