"""
SQL 执行结果验证服务

验证查询结果的合理性，提供有意义的反馈：
1. 空结果分析
2. 数据类型检查
3. 行数限制警告

使用方式：
    from app.services.result_validator import result_validator
    
    validation = result_validator.validate(
        result=execution_result,
        sql=generated_sql,
        user_query=user_query
    )
    
    if validation.has_issues:
        print(validation.message)
"""
import re
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ResultValidation:
    """结果验证信息"""
    is_valid: bool = True
    has_issues: bool = False
    message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    # 结果统计
    row_count: int = 0
    column_count: int = 0
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)
        self.has_issues = True
    
    def add_suggestion(self, suggestion: str):
        self.suggestions.append(suggestion)


class ResultValidator:
    """
    SQL 执行结果验证器
    
    功能：
    1. 空结果分析 - 提供可能原因
    2. 数据类型检查 - 确保格式正确
    3. 行数限制 - 超过阈值时警告
    """
    
    # 行数阈值
    LARGE_RESULT_THRESHOLD = 500
    VERY_LARGE_RESULT_THRESHOLD = 5000
    
    def validate(
        self,
        result: Any,
        sql: str = "",
        user_query: str = ""
    ) -> ResultValidation:
        """
        验证执行结果
        
        Args:
            result: SQL 执行结果（SQLExecutionResult 或 dict）
            sql: 执行的 SQL 语句
            user_query: 用户原始查询
            
        Returns:
            ResultValidation: 验证结果
        """
        validation = ResultValidation()
        
        # 提取结果数据
        data = self._extract_data(result)
        
        if data is None:
            validation.is_valid = False
            validation.message = "无法解析执行结果"
            return validation
        
        columns = data.get("columns", [])
        rows = data.get("data", [])
        row_count = data.get("row_count", len(rows))
        
        validation.row_count = row_count
        validation.column_count = len(columns)
        
        # 1. 空结果分析
        if row_count == 0:
            self._analyze_empty_result(validation, sql, user_query)
        
        # 2. 数据类型检查
        self._check_data_types(validation, columns, rows)
        
        # 3. 行数限制检查
        self._check_row_count(validation, row_count)
        
        # 4. 数据质量检查
        self._check_data_quality(validation, columns, rows)
        
        return validation
    
    def _extract_data(self, result: Any) -> Optional[Dict[str, Any]]:
        """从执行结果中提取数据"""
        if result is None:
            return None
        
        # SQLExecutionResult 对象
        if hasattr(result, 'data'):
            data = result.data
            if isinstance(data, dict):
                return data
            return {"data": data, "columns": [], "row_count": 0}
        
        # 字典格式
        if isinstance(result, dict):
            if "data" in result:
                inner_data = result["data"]
                if isinstance(inner_data, dict):
                    return inner_data
                return {"data": inner_data, "columns": [], "row_count": 0}
            return result
        
        return None
    
    def _analyze_empty_result(
        self,
        validation: ResultValidation,
        sql: str,
        user_query: str
    ):
        """分析空结果的可能原因"""
        validation.has_issues = True
        
        reasons = []
        suggestions = []
        
        sql_upper = sql.upper() if sql else ""
        query_lower = user_query.lower() if user_query else ""
        
        # 检查是否有严格的 WHERE 条件
        if "WHERE" in sql_upper:
            reasons.append("WHERE 条件可能过于严格")
            suggestions.append("尝试放宽筛选条件")
            
            # 检查日期条件
            if any(kw in sql_upper for kw in ['DATE', 'TIME', 'YEAR', 'MONTH', 'DAY']):
                reasons.append("日期范围可能不包含数据")
                suggestions.append("检查日期范围是否正确")
            
            # 检查等值条件
            if "=" in sql_upper and "!=" not in sql_upper and "<>" not in sql_upper:
                reasons.append("精确匹配条件可能没有匹配项")
                suggestions.append("尝试使用 LIKE 进行模糊匹配")
        
        # 检查是否有 LIMIT 0
        if re.search(r'\bLIMIT\s+0\b', sql_upper):
            reasons.append("LIMIT 设置为 0")
            suggestions.append("移除或调整 LIMIT 值")
        
        # 检查是否有 HAVING 条件
        if "HAVING" in sql_upper:
            reasons.append("HAVING 条件可能过滤了所有分组")
            suggestions.append("检查 HAVING 条件是否合理")
        
        # 检查用户查询中的特定词汇
        if any(word in query_lower for word in ['今天', '今日', 'today']):
            suggestions.append("确认今天是否有相关数据")
        
        if any(word in query_lower for word in ['最近', '近期', 'recent']):
            suggestions.append("尝试扩大时间范围")
        
        # 构建消息
        if reasons:
            validation.message = f"查询结果为空。可能原因：{'; '.join(reasons)}"
        else:
            validation.message = "查询结果为空，数据库中可能没有符合条件的数据"
        
        validation.suggestions = suggestions
    
    def _check_data_types(
        self,
        validation: ResultValidation,
        columns: List[str],
        rows: List[Any]
    ):
        """检查数据类型一致性"""
        if not rows or not columns:
            return
        
        # 取样检查（最多检查前 10 行）
        sample_rows = rows[:10]
        
        for row in sample_rows:
            # 处理列表格式
            if isinstance(row, list):
                if len(row) != len(columns):
                    validation.add_warning(f"数据列数（{len(row)}）与列名数（{len(columns)}）不匹配")
                    break
            # 处理字典格式
            elif isinstance(row, dict):
                missing_cols = set(columns) - set(row.keys())
                if missing_cols:
                    validation.add_warning(f"部分列缺少数据: {', '.join(list(missing_cols)[:3])}")
                    break
    
    def _check_row_count(self, validation: ResultValidation, row_count: int):
        """检查行数是否在合理范围"""
        if row_count >= self.VERY_LARGE_RESULT_THRESHOLD:
            validation.add_warning(f"结果集较大（{row_count} 行），可能影响展示性能")
            validation.add_suggestion("考虑添加更多筛选条件或使用分页")
        elif row_count >= self.LARGE_RESULT_THRESHOLD:
            validation.add_warning(f"结果集包含 {row_count} 行数据")
    
    def _check_data_quality(
        self,
        validation: ResultValidation,
        columns: List[str],
        rows: List[Any]
    ):
        """检查数据质量"""
        if not rows or not columns:
            return
        
        # 检查 NULL 值比例
        null_counts = {col: 0 for col in columns}
        total_rows = len(rows)
        
        for row in rows[:100]:  # 只检查前 100 行
            if isinstance(row, list):
                for i, val in enumerate(row):
                    if i < len(columns) and val is None:
                        null_counts[columns[i]] += 1
            elif isinstance(row, dict):
                for col in columns:
                    if row.get(col) is None:
                        null_counts[col] += 1
        
        # 报告高 NULL 比例的列
        sample_size = min(total_rows, 100)
        for col, count in null_counts.items():
            if sample_size > 0:
                null_ratio = count / sample_size
                if null_ratio > 0.5:
                    validation.add_warning(f"列 '{col}' 有较多空值（{null_ratio:.0%}）")


# 全局单例
result_validator = ResultValidator()


# 便捷函数
def validate_result(
    result: Any,
    sql: str = "",
    user_query: str = ""
) -> ResultValidation:
    """
    验证执行结果（便捷函数）
    
    Args:
        result: SQL 执行结果
        sql: 执行的 SQL 语句
        user_query: 用户原始查询
        
    Returns:
        ResultValidation
    """
    return result_validator.validate(result, sql, user_query)
