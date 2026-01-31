"""
SQL验证代理
负责验证生成的SQL语句的语法正确性、安全性和数据库方言兼容性

职责：
1. 语法验证：检查 SQL 基本语法（括号、引号、关键字等）
2. 安全验证：检查危险操作（DROP、DELETE 等）
3. 方言验证：检查 SQL 是否符合目标数据库语法（如 MySQL 不支持 IN 子查询中的 LIMIT）
4. 自动修复：尝试修复简单问题（如自动添加 LIMIT）
"""
import sqlparse
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, SQLValidationResult
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.services.sql_validator import sql_validator as sql_validator_service
from app.services.db_dialect import get_dialect, validate_dialect_compatibility


@tool
def validate_sql_syntax(
    sql_query: str, 
    db_type: str = "mysql",
    schema_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    验证SQL语法正确性、安全性、数据库方言兼容性，以及表名/列名是否存在
    
    Args:
        sql_query: SQL查询语句
        db_type: 数据库类型（mysql, postgresql, sqlserver, oracle, sqlite）
        schema_context: Schema 上下文（包含 tables, columns 信息），用于验证表名/列名
        
    Returns:
        验证结果，包含错误、警告和修复后的SQL
    """
    try:
        # 使用增强的 sql_validator 服务进行完整验证
        result = sql_validator_service.validate(
            sql=sql_query,
            schema_context=schema_context,  # 传入 schema_context 启用表名/列名验证
            db_type=db_type,
            allow_write=False  # 只读模式
        )
        
        return {
            "success": True,
            "is_valid": result.is_valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "fixed_sql": result.fixed_sql,  # 自动修复后的 SQL（如添加 LIMIT）
            "db_type": db_type
        }
        
    except Exception as e:
        return {
            "success": False,
            "is_valid": False,
            "error": str(e),
            "errors": [str(e)],
            "warnings": []
        }


@tool
def fix_sql_issues(sql_query: str, validation_errors: List[str]) -> Dict[str, Any]:
    """
    尝试修复SQL中的问题
    
    Args:
        sql_query: 原始SQL查询
        validation_errors: 验证错误列表
        
    Returns:
        修复后的SQL和修复说明
    """
    try:
        fixed_sql = sql_query
        fixes_applied = []
        
        # 修复常见问题
        for error in validation_errors:
            if "括号不匹配" in error:
                # 简单的括号修复逻辑
                open_count = fixed_sql.count('(')
                close_count = fixed_sql.count(')')
                if open_count > close_count:
                    fixed_sql += ')' * (open_count - close_count)
                    fixes_applied.append("添加缺失的右括号")
                elif close_count > open_count:
                    fixed_sql = '(' * (close_count - open_count) + fixed_sql
                    fixes_applied.append("添加缺失的左括号")
            
            elif "缺少SELECT语句" in error:
                if not fixed_sql.upper().strip().startswith('SELECT'):
                    fixed_sql = 'SELECT * FROM (' + fixed_sql + ') AS subquery'
                    fixes_applied.append("添加SELECT语句")
            
            elif "建议添加LIMIT子句" in error:
                if 'LIMIT' not in fixed_sql.upper():
                    fixed_sql += ' LIMIT 100'
                    fixes_applied.append("添加LIMIT子句")
        
        return {
            "success": True,
            "fixed_sql": fixed_sql,
            "fixes_applied": fixes_applied,
            "original_sql": sql_query
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


class SQLValidatorAgent:
    """SQL验证代理 - 负责语法验证、安全验证和方言兼容性验证"""

    def __init__(self):
        self.name = "sql_validator_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [
            validate_sql_syntax,
            fix_sql_issues
        ]
        
        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业的SQL验证专家。你的任务是：

1. 验证SQL语句的语法正确性
2. 验证SQL语句的安全性（禁止危险操作）
3. 验证SQL语句的数据库方言兼容性

验证流程：
1. 使用 validate_sql_syntax 检查语法、安全性和方言兼容性
2. 如有问题，使用 fix_sql_issues 尝试修复

验证标准：
- 语法必须正确
- 不能包含危险操作（DROP、DELETE、UPDATE 等）
- 必须符合目标数据库的语法规则（如 MySQL 不支持 IN 子查询中的 LIMIT）
- 只能使用 schema 中定义的表和列

如果发现问题，请提供具体的修复建议。"""
    
    def _build_schema_context(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        从 state 中构建 schema_context 用于表名/列名验证
        
        Returns:
            包含 tables, columns, relationships 的字典
        """
        schema_info = state.get("schema_info", {})
        
        if not schema_info:
            return None
        
        # 从 schema_info 中提取表和列信息
        tables = []
        columns = []
        relationships = []
        
        # 处理 schema_context 格式（全库检索模式）
        schema_context = schema_info.get("schema_context", {})
        if isinstance(schema_context, dict):
            for table_name, table_data in schema_context.items():
                if isinstance(table_data, dict):
                    tables.append({
                        "table_name": table_name,
                        "description": table_data.get("description", "")
                    })
                    for col in table_data.get("columns", []):
                        if isinstance(col, dict):
                            columns.append({
                                "table_name": table_name,
                                "column_name": col.get("column_name", col.get("name", "")),
                                "data_type": col.get("data_type", col.get("type", ""))
                            })
        
        # 处理 skill_tables 格式（Skill 模式）
        if not tables and schema_info.get("skill_tables"):
            for table_name in schema_info.get("skill_tables", []):
                tables.append({"table_name": table_name})
        
        # 获取关系信息
        relationships = schema_info.get("relationships", [])
        
        if not tables:
            return None
        
        return {
            "tables": tables,
            "columns": columns,
            "relationships": relationships
        }

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理SQL验证任务"""
        try:
            # 获取生成的SQL
            sql_query = state.get("generated_sql")
            if not sql_query:
                raise ValueError("没有找到需要验证的SQL语句")
            
            # 获取数据库类型
            db_type = state.get("db_type", "mysql")
            
            # 获取 schema_context 用于表名/列名验证
            schema_context = self._build_schema_context(state)

            # 使用增强的验证服务
            syntax_result = await validate_sql_syntax.ainvoke({
                "sql_query": sql_query,
                "db_type": db_type,
                "schema_context": schema_context
            })

            if not syntax_result.get("success", False):
                raise ValueError(syntax_result.get("error", "SQL验证失败"))

            errors = syntax_result.get("errors", [])
            warnings = syntax_result.get("warnings", [])
            fixed_sql = syntax_result.get("fixed_sql") or sql_query
            fixes_applied = []

            # 如果有错误，尝试修复
            if errors:
                fix_result = await fix_sql_issues.ainvoke({
                    "sql_query": sql_query,
                    "validation_errors": errors
                })
                if fix_result.get("success"):
                    fixes_applied = fix_result.get("fixes_applied", [])
                    candidate_sql = fix_result.get("fixed_sql", sql_query)
                    
                    # 重新验证修复后的 SQL
                    if candidate_sql != sql_query:
                        revalidate_result = await validate_sql_syntax.ainvoke({
                            "sql_query": candidate_sql,
                            "db_type": db_type,
                            "schema_context": schema_context
                        })
                        if revalidate_result.get("is_valid"):
                            fixed_sql = candidate_sql
                            errors = revalidate_result.get("errors", [])
                            warnings = revalidate_result.get("warnings", [])
            
            # 如果服务返回了 fixed_sql（如自动添加 LIMIT），使用它
            elif syntax_result.get("fixed_sql") and syntax_result.get("fixed_sql") != sql_query:
                fixed_sql = syntax_result.get("fixed_sql")
                fixes_applied.append("自动添加结果限制")

            is_valid = len(errors) == 0
            validation_result = SQLValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                suggestions=fixes_applied
            )

            state["validation_result"] = validation_result
            if is_valid:
                state["current_stage"] = "sql_execution"
                if fixed_sql != sql_query:
                    state["generated_sql"] = fixed_sql
            else:
                state["current_stage"] = "error_recovery"

            state["agent_messages"]["sql_validator"] = {
                "syntax_result": syntax_result,
                "fixes_applied": fixes_applied,
                "db_type": db_type
            }

            # 构建摘要
            summary = f"SQL验证通过（{db_type}）"
            if fixes_applied:
                summary = f"SQL验证通过，已修复: {', '.join(fixes_applied)}"
            if not is_valid and errors:
                summary = f"SQL验证失败: {errors[0]}"

            return {
                "messages": [AIMessage(content=summary)],
                "validation_result": validation_result,
                "current_stage": state["current_stage"]
            }
            
        except Exception as e:
            # 记录错误
            error_info = {
                "stage": "sql_validation",
                "error": str(e),
                "retry_count": state.get("retry_count", 0)
            }
            
            state["error_history"].append(error_info)
            state["current_stage"] = "error_recovery"
            
            return {
                "messages": [AIMessage(content=f"SQL验证失败: {str(e)}")],
                "current_stage": "error_recovery"
            }
    
# 创建全局实例
sql_validator_agent = SQLValidatorAgent()
