"""
SQL验证代理
负责验证生成的SQL语句的语法正确性、安全性和数据库方言兼容性

职责（简化版）：
1. 安全验证：检查危险操作（DROP、DELETE 等）
2. 资源限制：确保有 LIMIT 限制
3. 方言验证：检查 SQL 是否符合目标数据库语法

注意：复杂的语法检查交给 LLM 处理，避免规则引擎误报
"""
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, SQLValidationResult
from app.core.agent_config import get_agent_llm, CORE_AGENT_SQL_GENERATOR
from app.services.sql_validator import sql_validator as sql_validator_service


@tool
def validate_sql_syntax(
    sql_query: str, 
    db_type: str = "mysql",
    schema_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    验证SQL安全性、资源限制、数据库方言兼容性，以及表名/列名是否存在
    
    Args:
        sql_query: SQL查询语句
        db_type: 数据库类型（mysql, postgresql, sqlserver, oracle, sqlite）
        schema_context: Schema 上下文（包含 tables, columns 信息），用于验证表名/列名
        
    Returns:
        验证结果，包含错误、警告和修复后的SQL
    """
    try:
        result = sql_validator_service.validate(
            sql=sql_query,
            schema_context=schema_context,
            db_type=db_type,
            allow_write=False
        )
        
        return {
            "success": True,
            "is_valid": result.is_valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "fixed_sql": result.fixed_sql,
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


class SQLValidatorAgent:
    """
    SQL验证代理 - 简化版
    
    验证逻辑：
    1. 调用 validate_sql_syntax 进行安全检查、资源限制、方言兼容性验证
    2. 如果有错误 → 进入 error_recovery
    3. 如果通过 → 进入 sql_execution
    
    注意：不再使用复杂的规则引擎进行语法检查，避免误报
    """

    def __init__(self):
        self.name = "sql_validator_agent"
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.tools = [validate_sql_syntax]
        
        # 创建 ReAct agent（保持接口兼容）
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是SQL验证专家。验证SQL的安全性和方言兼容性。
        
使用 validate_sql_syntax 工具检查SQL。只输出验证结果，不解释SQL逻辑。"""
    
    def _build_schema_context(self, state: SQLMessageState) -> Dict[str, Any]:
        """从 state 中构建 schema_context 用于表名/列名验证"""
        schema_info = state.get("schema_info", {})
        
        if not schema_info:
            return None
        
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
        
        relationships = schema_info.get("relationships", [])
        
        if not tables:
            return None
        
        return {
            "tables": tables,
            "columns": columns,
            "relationships": relationships
        }

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理SQL验证任务（简化流程）"""
        try:
            sql_query = state.get("generated_sql")
            if not sql_query:
                raise ValueError("没有找到需要验证的SQL语句")
            
            db_type = state.get("db_type", "mysql")
            schema_context = self._build_schema_context(state)

            # 调用验证服务
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

            is_valid = len(errors) == 0
            validation_result = SQLValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                suggestions=[]
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
                "db_type": db_type
            }

            # 构建摘要
            if is_valid:
                summary = f"SQL验证通过（{db_type}）"
                if fixed_sql != sql_query:
                    summary = f"SQL验证通过，已自动添加 LIMIT 限制"
            else:
                summary = f"SQL验证失败: {errors[0]}"

            return {
                "messages": [AIMessage(content=summary)],
                "validation_result": validation_result,
                "current_stage": state["current_stage"]
            }
            
        except Exception as e:
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
