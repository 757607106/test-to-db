"""
SQL验证代理
负责验证生成的SQL语句的正确性、安全性和性能
"""
import re
import sqlparse
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from app.core.state import SQLMessageState, SQLValidationResult
from app.core.llms import get_default_model

@tool
def validate_sql_syntax(sql_query: str, db_type: str = "mysql") -> Dict[str, Any]:
    """
    验证SQL语法正确性
    
    Args:
        sql_query: SQL查询语句
        db_type: 数据库类型
        
    Returns:
        语法验证结果
    """
    try:
        errors = []
        warnings = []
        
        # 使用sqlparse进行基础语法检查
        try:
            parsed = sqlparse.parse(sql_query)
            if not parsed:
                errors.append("SQL语句无法解析")
        except Exception as e:
            errors.append(f"SQL语法错误: {str(e)}")
        
        # 检查常见的SQL问题
        sql_upper = sql_query.upper()
        
        # 检查是否包含危险操作
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                errors.append(f"包含危险操作: {keyword}")
        
        # 检查是否有SELECT语句
        if 'SELECT' not in sql_upper:
            errors.append("缺少SELECT语句")
        
        # 检查括号匹配
        if sql_query.count('(') != sql_query.count(')'):
            errors.append("括号不匹配")
        
        # 检查引号匹配
        single_quotes = sql_query.count("'")
        double_quotes = sql_query.count('"')
        if single_quotes % 2 != 0:
            warnings.append("单引号可能不匹配")
        if double_quotes % 2 != 0:
            warnings.append("双引号可能不匹配")
        
        # 检查是否有LIMIT子句（推荐）
        if 'LIMIT' not in sql_upper and 'TOP' not in sql_upper:
            warnings.append("建议添加LIMIT子句以限制结果集大小")
        
        return {
            "success": True,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@tool
def validate_sql_security(sql_query: str) -> Dict[str, Any]:
    """
    验证SQL安全性，检查SQL注入风险
    
    Args:
        sql_query: SQL查询语句
        
    Returns:
        安全性验证结果
    """
    try:
        security_issues = []
        warnings = []
        
        # 检查SQL注入模式
        injection_patterns = [
            r"';.*--",  # 注释注入
            r"union.*select",  # UNION注入
            r"or.*1=1",  # 逻辑注入
            r"and.*1=1",  # 逻辑注入
            r"exec\s*\(",  # 执行函数
            r"sp_",  # 存储过程
            r"xp_",  # 扩展存储过程
        ]
        
        sql_lower = sql_query.lower()
        for pattern in injection_patterns:
            if re.search(pattern, sql_lower):
                security_issues.append(f"检测到潜在的SQL注入模式: {pattern}")
        
        # 检查动态SQL构造
        if "concat" in sql_lower or "||" in sql_query:
            warnings.append("检测到字符串拼接，请确保输入已正确转义")
        
        # 检查用户输入直接嵌入
        if "'" in sql_query and not re.search(r"'[^']*'", sql_query):
            warnings.append("检测到可能的未转义用户输入")
        
        return {
            "success": True,
            "is_secure": len(security_issues) == 0,
            "security_issues": security_issues,
            "warnings": warnings
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@tool
def validate_sql_performance(sql_query: str, schema_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    验证SQL性能，识别潜在的性能问题

    Args:
        sql_query: SQL查询语句
        schema_info: 模式信息
        
    Returns:
        性能验证结果
    """

    # 建议调用数据库的性能测试工具：mysql的 explain ，改造一下

    try:
        performance_issues = []
        suggestions = []
        
        sql_upper = sql_query.upper()
        
        # 检查是否使用SELECT *
        if re.search(r'SELECT\s+\*', sql_upper):
            performance_issues.append("使用SELECT *可能影响性能，建议明确指定需要的列")
        
        # 检查是否有WHERE子句
        if 'WHERE' not in sql_upper and 'LIMIT' not in sql_upper:
            performance_issues.append("缺少WHERE子句可能导致全表扫描")
        
        # 检查JOIN类型
        if 'CROSS JOIN' in sql_upper:
            performance_issues.append("CROSS JOIN可能产生笛卡尔积，影响性能")
        
        # 检查子查询
        subquery_count = sql_query.count('(SELECT')
        if subquery_count > 2:
            suggestions.append(f"检测到{subquery_count}个子查询，考虑使用JOIN优化")

        # 检查ORDER BY
        if 'ORDER BY' in sql_upper and 'LIMIT' not in sql_upper:
            suggestions.append("ORDER BY without LIMIT可能影响性能")
        
        # 检查LIKE模式
        like_patterns = re.findall(r"LIKE\s+'([^']*)'", sql_upper)
        for pattern in like_patterns:
            if pattern.startswith('%'):
                performance_issues.append(f"LIKE模式'{pattern}'以通配符开头，无法使用索引")
        
        return {
            "success": True,
            "performance_score": max(0, 100 - len(performance_issues) * 20),
            "performance_issues": performance_issues,
            "suggestions": suggestions
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
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

@tool
def human_feedback(state):
    """
    需要用户参与解决sql出现的的问题
    :param state:
    :return:
    """
    pass

class SQLValidatorAgent:
    """SQL验证代理"""

    def __init__(self):
        self.name = "sql_validator_agent"  # 添加name属性
        self.llm = get_default_model()
        self.tools = [
            validate_sql_syntax, 
            validate_sql_security, 
            validate_sql_performance, 
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
2. 检查SQL的安全性，防止SQL注入
3. 分析SQL的性能，识别潜在问题
4. 修复发现的问题

验证流程：
1. 使用 validate_sql_syntax 检查语法
2. 使用 validate_sql_security 检查安全性
3. 使用 validate_sql_performance 分析性能
4. 如有问题，使用 fix_sql_issues 尝试修复

验证标准：
- 语法必须正确
- 不能包含危险操作
- 应该有适当的性能优化
- 必须防止SQL注入

如果发现问题，请提供具体的修复建议。"""

    async def process(self, state: SQLMessageState) -> Dict[str, Any]:
        """处理SQL验证任务"""
        try:
            # 获取生成的SQL
            sql_query = state.get("generated_sql")
            if not sql_query:
                raise ValueError("没有找到需要验证的SQL语句")
            
            # 准备输入消息
            messages = [
                HumanMessage(content=f"""
请验证以下SQL语句的正确性、安全性和性能：

SQL语句:
{sql_query}

请进行全面的验证并提供修复建议。
""")
            ]
            
            # 调用代理
            result = await self.agent.ainvoke({
                "messages": messages
            })
            
            # 创建验证结果
            validation_result = self._create_validation_result(result)
            
            # 更新状态
            state["validation_result"] = validation_result
            if validation_result.is_valid:
                state["current_stage"] = "sql_execution"
            else:
                state["current_stage"] = "error_recovery"
            
            state["agent_messages"]["sql_validator"] = result
            
            return {
                "messages": result["messages"],
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
    
    def _create_validation_result(self, result: Dict[str, Any]) -> SQLValidationResult:
        """从代理结果创建验证结果对象"""
        # 简化实现，实际应该解析代理的详细输出
        messages = result.get("messages", [])
        
        errors = []
        warnings = []
        suggestions = []
        is_valid = True
        
        for message in messages:
            if hasattr(message, 'content'):
                content = message.content.lower()
                if "错误" in content or "error" in content:
                    errors.append(message.content)
                    is_valid = False
                elif "警告" in content or "warning" in content:
                    warnings.append(message.content)
                elif "建议" in content or "suggestion" in content:
                    suggestions.append(message.content)
        
        return SQLValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )

# 创建全局实例
sql_validator_agent = SQLValidatorAgent()
