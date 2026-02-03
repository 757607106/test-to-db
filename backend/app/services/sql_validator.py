"""
SQL 验证服务 - LLM 驱动版本

在 SQL 执行前进行验证，确保：
1. 安全（无危险操作）- 硬编码规则
2. 资源可控（有 LIMIT 限制）- 硬编码规则
3. 语法正确、列名/表名存在 - LLM 验证

使用方式：
    from app.services.sql_validator import sql_validator
    
    result = sql_validator.validate(
        sql="SELECT * FROM products",
        schema_context=schema_context,
        db_type="mysql"
    )
    
    if not result.is_valid:
        print(result.errors)
"""
import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SQLValidationResult:
    """SQL 验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fixed_sql: Optional[str] = None  # 自动修复后的 SQL（如添加 LIMIT）
    
    def add_error(self, error: str):
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)


class SQLValidator:
    """
    SQL 验证器 - LLM 驱动
    
    验证层级：
    1. 安全检查（禁止危险操作）- 硬编码规则
    2. 资源限制检查 - 硬编码规则
    3. 语法和 Schema 一致性 - 跳过（交给 LLM 和数据库处理）
    
    设计原则：
    - 硬编码规则只做最基本的安全检查
    - 不做复杂的语法、表名、列名验证（容易误报）
    - 让 LLM 和数据库本身来处理复杂的验证
    """
    
    # 禁止的危险关键字（只读模式）
    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 
        'INSERT', 'UPDATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE'
    ]
    
    # 默认 LIMIT 值
    DEFAULT_LIMIT = 1000
    MAX_LIMIT = 10000
    
    def validate(
        self,
        sql: str,
        schema_context: Optional[Dict[str, Any]] = None,
        db_type: str = "mysql",
        allow_write: bool = False
    ) -> SQLValidationResult:
        """
        验证 SQL 语句
        
        Args:
            sql: SQL 语句
            schema_context: Schema 上下文（不再用于验证，仅供参考）
            db_type: 数据库类型
            allow_write: 是否允许写操作（默认只读）
            
        Returns:
            SQLValidationResult: 验证结果
        """
        result = SQLValidationResult(is_valid=True)
        
        if not sql or not sql.strip():
            result.add_error("SQL 语句为空")
            return result
        
        sql = sql.strip()
        
        # 1. 基础格式检查（只检查是否是 SELECT 语句）
        sql_upper = sql.upper().strip()
        if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
            result.add_error(f"只支持 SELECT 查询，当前语句以 '{sql_upper.split()[0] if sql_upper else '空'}' 开头")
            return result
        
        # 2. 安全检查
        if not allow_write:
            self._check_security(sql, result)
            if not result.is_valid:
                return result
        
        # 3. 资源限制检查（自动添加 LIMIT）
        fixed_sql = self._check_resource_limits(sql, db_type, result)
        if fixed_sql:
            result.fixed_sql = fixed_sql
        
        # 4. 不再做复杂的 Schema 一致性检查
        # 让 SQL 执行时由数据库本身来验证表名和列名
        # 这样可以避免误报，也能获得更准确的错误信息
        
        return result
    
    def _check_security(self, sql: str, result: SQLValidationResult):
        """安全检查 - 禁止危险操作"""
        sql_upper = sql.upper()
        
        for keyword in self.DANGEROUS_KEYWORDS:
            # 使用单词边界匹配，避免误判（如 UPDATED_AT 列名）
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                result.add_error(f"安全限制：禁止使用 {keyword} 操作")
                return
        
        # 检查是否有多语句（分号分隔）
        # 移除字符串中的分号后检查
        sql_no_strings = re.sub(r"'[^']*'", '', sql)
        if ';' in sql_no_strings.rstrip(';'):
            result.add_error("安全限制：禁止执行多条 SQL 语句")
    
    def _check_resource_limits(
        self, 
        sql: str, 
        db_type: str,
        result: SQLValidationResult
    ) -> Optional[str]:
        """
        资源限制检查
        
        确保 SELECT 查询有 LIMIT 限制，防止返回过多数据
        
        Returns:
            Optional[str]: 修复后的 SQL（如果添加了 LIMIT）
        """
        sql_upper = sql.upper()
        
        # 检查是否已有 LIMIT/TOP/FETCH
        has_limit = bool(re.search(r'\bLIMIT\s+\d+', sql_upper))
        has_top = bool(re.search(r'\bTOP\s+\d+', sql_upper))
        has_fetch = bool(re.search(r'\bFETCH\s+(FIRST|NEXT)\s+\d+', sql_upper))
        
        if has_limit or has_top or has_fetch:
            # 检查 LIMIT 值是否过大
            limit_match = re.search(r'\bLIMIT\s+(\d+)', sql_upper)
            if limit_match:
                limit_value = int(limit_match.group(1))
                if limit_value > self.MAX_LIMIT:
                    result.add_warning(f"LIMIT 值 ({limit_value}) 超过推荐最大值 ({self.MAX_LIMIT})")
            return None
        
        # 没有 LIMIT，需要添加
        result.add_warning(f"已自动添加 LIMIT {self.DEFAULT_LIMIT} 限制")
        
        return self._add_limit(sql, db_type)
    
    def _add_limit(self, sql: str, db_type: str) -> str:
        """为 SQL 添加 LIMIT 限制"""
        sql = sql.rstrip().rstrip(';')
        db_type_lower = db_type.lower() if db_type else 'mysql'
        
        if db_type_lower == 'sqlserver':
            # SQL Server 使用 TOP
            if sql.upper().startswith('SELECT'):
                return sql.replace('SELECT', f'SELECT TOP {self.DEFAULT_LIMIT}', 1)
            return sql
        elif db_type_lower == 'oracle':
            # Oracle 12c+ 使用 FETCH FIRST
            return f"{sql} FETCH FIRST {self.DEFAULT_LIMIT} ROWS ONLY"
        else:
            # MySQL, PostgreSQL, SQLite 使用 LIMIT
            return f"{sql} LIMIT {self.DEFAULT_LIMIT}"


# 创建全局实例
sql_validator = SQLValidator()
