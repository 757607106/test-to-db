"""
数据库管理器
集成现有的dbaccess.py功能，为代理系统提供统一的数据库访问接口
"""
import time
import pandas as pd
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.db.dbaccess import DBAccess
from app.core.state import SQLExecutionResult


@dataclass
class DatabaseConfig:
    """数据库配置"""
    db_type: str  # mysql, postgres, sqlite, etc.
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    connection_string: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None


class DatabaseManager:
    """数据库管理器 - 封装dbaccess.py的功能"""
    
    def __init__(self):
        self.db_access = None
        self.current_config = None
        self.connection_pool = {}  # 连接池，支持多个数据库连接
    
    def connect(self, config: DatabaseConfig) -> bool:
        """
        连接到数据库
        
        Args:
            config: 数据库配置
            
        Returns:
            连接是否成功
        """
        try:
            self.db_access = DBAccess()

            
            if config.db_type.lower() == "mysql":
                self.db_access.connect_to_mysql(
                    host=config.host or "localhost",
                    dbname=config.database or "Chinook",
                    user=config.username or "root", 
                    password=config.password or "mysql",
                    port=config.port or 3306,
                    **(config.additional_params or {})
                )
            elif config.db_type.lower() == "postgres":
                self.db_access.connect_to_postgres(
                    host=config.host,
                    dbname=config.database,
                    user=config.username,
                    password=config.password,
                    port=config.port or 5432,
                    **(config.additional_params or {})
                )
            elif config.db_type.lower() == "sqlite":
                self.db_access.connect_to_sqlite(
                    url=config.connection_string or config.database,
                    **(config.additional_params or {})
                )
            elif config.db_type.lower() == "snowflake":
                self.db_access.connect_to_snowflake(
                    account=config.additional_params.get("account"),
                    username=config.username,
                    password=config.password,
                    database=config.database,
                    role=config.additional_params.get("role"),
                    warehouse=config.additional_params.get("warehouse")
                )
            elif config.db_type.lower() == "bigquery":
                self.db_access.connect_to_bigquery(
                    project_id=config.additional_params.get("project_id"),
                    cred_file_path=config.additional_params.get("cred_file_path")
                )
            elif config.db_type.lower() == "oracle":
                self.db_access.connect_to_oracle(
                    user=config.username,
                    password=config.password,
                    dsn=config.connection_string
                )
            elif config.db_type.lower() == "clickhouse":
                self.db_access.connect_to_clickhouse(
                    host=config.host,
                    dbname=config.database,
                    user=config.username,
                    password=config.password,
                    port=config.port or 8123
                )
            elif config.db_type.lower() == "duckdb":
                self.db_access.connect_to_duckdb(
                    url=config.connection_string or ":memory:",
                    init_sql=config.additional_params.get("init_sql")
                )
            else:
                raise ValueError(f"不支持的数据库类型: {config.db_type}")
            
            self.current_config = config
            return True
            
        except Exception as e:
            print(f"数据库连接失败: {str(e)}")
            return False
    
    def execute_query(self, sql: str, timeout: int = 30) -> SQLExecutionResult:
        """
        执行SQL查询
        
        Args:
            sql: SQL查询语句
            timeout: 超时时间（秒）
            
        Returns:
            执行结果
        """
        if not self.db_access or not self.db_access.run_sql_is_set:
            return SQLExecutionResult(
                success=False,
                error="数据库未连接或连接无效"
            )
        
        start_time = time.time()

        try:
            # 执行查询
            result = self.db_access.run_sql(sql)
            execution_time = time.time() - start_time
            
            # 检查超时
            if execution_time > timeout:
                return SQLExecutionResult(
                    success=False,
                    error=f"查询超时 ({execution_time:.2f}秒 > {timeout}秒)",
                    execution_time=execution_time
                )
            
            # 处理结果
            if isinstance(result, pd.DataFrame):
                # 转换DataFrame为可序列化的格式
                data = {
                    "columns": result.columns.tolist(),
                    "data": result.values.tolist(),
                    "row_count": len(result),
                    "column_count": len(result.columns),
                    "dtypes": {col: str(dtype) for col, dtype in result.dtypes.items()}
                }
                
                return SQLExecutionResult(
                    success=True,
                    data=data,
                    execution_time=execution_time,
                    rows_affected=len(result)
                )
            else:
                # 非DataFrame结果
                return SQLExecutionResult(
                    success=True,
                    data={"raw_result": str(result)},
                    execution_time=execution_time,
                    rows_affected=0
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            return SQLExecutionResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def validate_connection(self) -> bool:
        """验证数据库连接是否有效"""
        try:
            if not self.db_access or not self.db_access.run_sql_is_set:
                return False
# pragma: no cover  Mi80OmFIVnBZMlhva3JMbW5iN21ucGM2VEhkTk1BPT06MjQ2MDkyYzc=
            
            # 执行简单的测试查询
            test_queries = {
                "mysql": "SELECT 1",
                "postgres": "SELECT 1",
                "sqlite": "SELECT 1",
                "oracle": "SELECT 1 FROM DUAL",
                "snowflake": "SELECT 1",
                "bigquery": "SELECT 1",
                "clickhouse": "SELECT 1",
                "duckdb": "SELECT 1"
            }
            
            db_type = self.current_config.db_type.lower() if self.current_config else "mysql"
            test_query = test_queries.get(db_type, "SELECT 1")
            
            result = self.execute_query(test_query, timeout=5)
            return result.success
            
        except Exception:
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        if not self.current_config:
            return {"connected": False}
        
        return {
            "connected": self.validate_connection(),
            "db_type": self.current_config.db_type,
            "database": self.current_config.database,
            "host": self.current_config.host,
            "port": self.current_config.port,
            "dialect": getattr(self.db_access, 'dialect', 'Unknown') if self.db_access else 'Unknown'
        }
    
    def close_connection(self):
        """关闭数据库连接"""
        # DBAccess类没有显式的关闭方法，但我们可以重置状态
        self.db_access = None
        self.current_config = None
    
    def get_table_info(self, table_name: str = None) -> Dict[str, Any]:
        """
        获取表信息
        
        Args:
            table_name: 表名，如果为None则获取所有表
            
        Returns:
            表信息
        """
        try:
            if table_name:
                # 获取特定表的信息
                info_queries = {
                    "mysql": f"DESCRIBE {table_name}",
                    "postgres": f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'",
                    "sqlite": f"PRAGMA table_info({table_name})"
                }
            else:
                # 获取所有表的列表
                info_queries = {
                    "mysql": "SHOW TABLES",
                    "postgres": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
                    "sqlite": "SELECT name FROM sqlite_master WHERE type='table'"
                }
            
            db_type = self.current_config.db_type.lower() if self.current_config else "mysql"
            query = info_queries.get(db_type, info_queries["mysql"])
            
            result = self.execute_query(query)
            
            if result.success:
                return {
                    "success": True,
                    "table_info": result.data
                }
            else:
                return {
                    "success": False,
                    "error": result.error
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# 全局数据库管理器实例
db_manager = DatabaseManager()

# pragma: no cover  My80OmFIVnBZMlhva3JMbW5iN21ucGM2VEhkTk1BPT06MjQ2MDkyYzc=

# 便捷函数
def get_default_db_config() -> DatabaseConfig:
    """获取默认数据库配置"""
    return DatabaseConfig(
        db_type="mysql",
        host="localhost",
        port=3306,
        database="Chinook",
        username="root",
        password="mysql"
    )


def ensure_db_connection() -> bool:
    """确保数据库连接"""
    if not db_manager.validate_connection():
        config = get_default_db_config()
        return db_manager.connect(config)
    return True
