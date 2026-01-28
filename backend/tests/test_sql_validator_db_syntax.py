"""
SQL Validator 数据库特定语法支持测试

测试 _add_limit 方法是否正确支持不同数据库类型的语法：
- MySQL: LIMIT
- PostgreSQL: LIMIT
- SQLite: LIMIT
- SQL Server: TOP
- Oracle: FETCH FIRST

Requirements: 8.1, 8.2
"""
import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.sql_validator import SQLValidator, sql_validator


class TestDatabaseSpecificSyntax:
    """测试数据库特定语法支持 - Requirements 8.1, 8.2"""
    
    def setup_method(self):
        """每个测试方法前初始化"""
        self.validator = SQLValidator()
        self.test_sql = "SELECT * FROM products"
    
    # ========================================================================
    # _add_limit 方法测试
    # ========================================================================
    
    def test_add_limit_mysql(self):
        """MySQL 应使用 LIMIT 语法"""
        result = self.validator._add_limit(self.test_sql, "mysql")
        assert "LIMIT" in result.upper()
        assert str(self.validator.DEFAULT_LIMIT) in result
        assert "TOP" not in result.upper()
        assert "FETCH FIRST" not in result.upper()
    
    def test_add_limit_postgresql(self):
        """PostgreSQL 应使用 LIMIT 语法"""
        result = self.validator._add_limit(self.test_sql, "postgresql")
        assert "LIMIT" in result.upper()
        assert str(self.validator.DEFAULT_LIMIT) in result
        assert "TOP" not in result.upper()
        assert "FETCH FIRST" not in result.upper()
    
    def test_add_limit_sqlite(self):
        """SQLite 应使用 LIMIT 语法"""
        result = self.validator._add_limit(self.test_sql, "sqlite")
        assert "LIMIT" in result.upper()
        assert str(self.validator.DEFAULT_LIMIT) in result
        assert "TOP" not in result.upper()
        assert "FETCH FIRST" not in result.upper()
    
    def test_add_limit_sqlserver(self):
        """SQL Server 应使用 TOP 语法"""
        result = self.validator._add_limit(self.test_sql, "sqlserver")
        assert "TOP" in result.upper()
        assert str(self.validator.DEFAULT_LIMIT) in result
        # TOP 应该在 SELECT 后面
        assert result.upper().startswith("SELECT TOP")
        assert "LIMIT" not in result.upper()
        assert "FETCH FIRST" not in result.upper()
    
    def test_add_limit_oracle(self):
        """Oracle 应使用 FETCH FIRST 语法"""
        result = self.validator._add_limit(self.test_sql, "oracle")
        assert "FETCH FIRST" in result.upper()
        assert "ROWS ONLY" in result.upper()
        assert str(self.validator.DEFAULT_LIMIT) in result
        assert "TOP" not in result.upper()
        # Oracle 不应该有单独的 LIMIT 关键字
        assert "LIMIT" not in result.upper() or "FETCH FIRST" in result.upper()
    
    def test_add_limit_unknown_db_defaults_to_limit(self):
        """未知数据库类型应默认使用 LIMIT 语法"""
        result = self.validator._add_limit(self.test_sql, "unknown_db")
        assert "LIMIT" in result.upper()
        assert str(self.validator.DEFAULT_LIMIT) in result
    
    # ========================================================================
    # 大小写不敏感测试
    # ========================================================================
    
    def test_add_limit_case_insensitive_mysql(self):
        """MySQL 数据库类型应大小写不敏感"""
        result1 = self.validator._add_limit(self.test_sql, "MySQL")
        result2 = self.validator._add_limit(self.test_sql, "MYSQL")
        result3 = self.validator._add_limit(self.test_sql, "mysql")
        
        assert "LIMIT" in result1.upper()
        assert "LIMIT" in result2.upper()
        assert "LIMIT" in result3.upper()
    
    def test_add_limit_case_insensitive_sqlserver(self):
        """SQL Server 数据库类型应大小写不敏感"""
        result1 = self.validator._add_limit(self.test_sql, "SQLServer")
        result2 = self.validator._add_limit(self.test_sql, "SQLSERVER")
        result3 = self.validator._add_limit(self.test_sql, "sqlserver")
        
        assert "TOP" in result1.upper()
        assert "TOP" in result2.upper()
        assert "TOP" in result3.upper()
    
    def test_add_limit_case_insensitive_oracle(self):
        """Oracle 数据库类型应大小写不敏感"""
        result1 = self.validator._add_limit(self.test_sql, "Oracle")
        result2 = self.validator._add_limit(self.test_sql, "ORACLE")
        result3 = self.validator._add_limit(self.test_sql, "oracle")
        
        assert "FETCH FIRST" in result1.upper()
        assert "FETCH FIRST" in result2.upper()
        assert "FETCH FIRST" in result3.upper()
    
    # ========================================================================
    # 复杂 SQL 测试
    # ========================================================================
    
    def test_add_limit_complex_sql_mysql(self):
        """MySQL 复杂 SQL 应正确添加 LIMIT"""
        complex_sql = "SELECT p.name, c.category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.price > 100"
        result = self.validator._add_limit(complex_sql, "mysql")
        assert result.endswith(f"LIMIT {self.validator.DEFAULT_LIMIT}")
    
    def test_add_limit_complex_sql_sqlserver(self):
        """SQL Server 复杂 SQL 应正确添加 TOP"""
        complex_sql = "SELECT p.name, c.category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.price > 100"
        result = self.validator._add_limit(complex_sql, "sqlserver")
        assert result.upper().startswith("SELECT TOP")
        # 确保只替换了第一个 SELECT
        assert result.upper().count("TOP") == 1
    
    def test_add_limit_complex_sql_oracle(self):
        """Oracle 复杂 SQL 应正确添加 FETCH FIRST"""
        complex_sql = "SELECT p.name, c.category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.price > 100"
        result = self.validator._add_limit(complex_sql, "oracle")
        assert result.upper().endswith("ROWS ONLY")
    
    # ========================================================================
    # 带分号的 SQL 测试
    # ========================================================================
    
    def test_add_limit_removes_trailing_semicolon(self):
        """应移除尾部分号后再添加 LIMIT"""
        sql_with_semicolon = "SELECT * FROM products;"
        
        result_mysql = self.validator._add_limit(sql_with_semicolon, "mysql")
        assert not result_mysql.endswith(";")
        assert "LIMIT" in result_mysql.upper()
        
        result_oracle = self.validator._add_limit(sql_with_semicolon, "oracle")
        assert not result_oracle.endswith(";")
        assert "FETCH FIRST" in result_oracle.upper()
    
    # ========================================================================
    # validate 方法集成测试
    # ========================================================================
    
    def test_validate_auto_adds_limit_mysql(self):
        """validate 方法应为 MySQL 自动添加 LIMIT"""
        result = self.validator.validate(self.test_sql, db_type="mysql")
        assert result.is_valid
        assert result.fixed_sql is not None
        assert "LIMIT" in result.fixed_sql.upper()
    
    def test_validate_auto_adds_limit_sqlserver(self):
        """validate 方法应为 SQL Server 自动添加 TOP"""
        result = self.validator.validate(self.test_sql, db_type="sqlserver")
        assert result.is_valid
        assert result.fixed_sql is not None
        assert "TOP" in result.fixed_sql.upper()
    
    def test_validate_auto_adds_limit_oracle(self):
        """validate 方法应为 Oracle 自动添加 FETCH FIRST"""
        result = self.validator.validate(self.test_sql, db_type="oracle")
        assert result.is_valid
        assert result.fixed_sql is not None
        assert "FETCH FIRST" in result.fixed_sql.upper()
    
    # ========================================================================
    # 已有 LIMIT/TOP/FETCH FIRST 的 SQL 测试
    # ========================================================================
    
    def test_validate_existing_limit_not_modified(self):
        """已有 LIMIT 的 SQL 不应被修改（除非超过最大值）"""
        sql_with_limit = "SELECT * FROM products LIMIT 100"
        result = self.validator.validate(sql_with_limit, db_type="mysql")
        assert result.is_valid
        assert result.fixed_sql is None  # 不需要修复
    
    def test_validate_existing_top_not_modified(self):
        """已有 TOP 的 SQL 不应被修改（除非超过最大值）"""
        sql_with_top = "SELECT TOP 100 * FROM products"
        result = self.validator.validate(sql_with_top, db_type="sqlserver")
        assert result.is_valid
        assert result.fixed_sql is None  # 不需要修复
    
    def test_validate_existing_fetch_first_not_modified(self):
        """已有 FETCH FIRST 的 SQL 不应被修改（除非超过最大值）"""
        sql_with_fetch = "SELECT * FROM products FETCH FIRST 100 ROWS ONLY"
        result = self.validator.validate(sql_with_fetch, db_type="oracle")
        assert result.is_valid
        assert result.fixed_sql is None  # 不需要修复
    
    # ========================================================================
    # 超过最大值的 LIMIT 测试
    # ========================================================================
    
    def test_validate_limit_exceeds_max_adjusted(self):
        """超过最大值的 LIMIT 应被调整"""
        sql_with_large_limit = f"SELECT * FROM products LIMIT {self.validator.MAX_LIMIT + 1000}"
        result = self.validator.validate(sql_with_large_limit, db_type="mysql")
        assert result.is_valid
        assert result.fixed_sql is not None
        assert str(self.validator.MAX_LIMIT) in result.fixed_sql
    
    def test_validate_top_exceeds_max_adjusted(self):
        """超过最大值的 TOP 应被调整"""
        sql_with_large_top = f"SELECT TOP {self.validator.MAX_LIMIT + 1000} * FROM products"
        result = self.validator.validate(sql_with_large_top, db_type="sqlserver")
        assert result.is_valid
        assert result.fixed_sql is not None
        assert str(self.validator.MAX_LIMIT) in result.fixed_sql
    
    def test_validate_fetch_first_exceeds_max_adjusted(self):
        """超过最大值的 FETCH FIRST 应被调整"""
        sql_with_large_fetch = f"SELECT * FROM products FETCH FIRST {self.validator.MAX_LIMIT + 1000} ROWS ONLY"
        result = self.validator.validate(sql_with_large_fetch, db_type="oracle")
        assert result.is_valid
        assert result.fixed_sql is not None
        assert str(self.validator.MAX_LIMIT) in result.fixed_sql


class TestSupportedDatabaseTypes:
    """测试支持的数据库类型列表 - Requirements 8.1"""
    
    def test_supported_db_types_contains_mysql(self):
        """应支持 MySQL"""
        assert 'mysql' in SQLValidator.SUPPORTED_DB_TYPES
    
    def test_supported_db_types_contains_postgresql(self):
        """应支持 PostgreSQL"""
        assert 'postgresql' in SQLValidator.SUPPORTED_DB_TYPES
    
    def test_supported_db_types_contains_sqlite(self):
        """应支持 SQLite"""
        assert 'sqlite' in SQLValidator.SUPPORTED_DB_TYPES
    
    def test_supported_db_types_contains_sqlserver(self):
        """应支持 SQL Server"""
        assert 'sqlserver' in SQLValidator.SUPPORTED_DB_TYPES
    
    def test_supported_db_types_contains_oracle(self):
        """应支持 Oracle"""
        assert 'oracle' in SQLValidator.SUPPORTED_DB_TYPES


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
