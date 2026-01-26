"""
值域预检索服务 (Value Profiling Service)

对数据库字段进行 Profile 分析，收集：
- 枚举值（低基数字段）
- 数值范围
- 日期范围
- 空值率
- 采样值

将 Profile 结果存储在 Neo4j 的 Column 节点上，供 Schema Agent 使用。
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from neo4j import GraphDatabase
from sqlalchemy import text

from app.core.config import settings
from app.services.db_service import get_db_engine, get_db_connection_by_id
from app.schemas.metric import ColumnProfile, TableProfile

logger = logging.getLogger(__name__)

# 低基数阈值：去重值少于此数量的字段被视为枚举字段
ENUM_THRESHOLD = 100

# Profile 查询的采样行数限制
SAMPLE_LIMIT = 10000


class ValueProfilingService:
    """值域预检索服务"""
    
    def __init__(self):
        self.neo4j_driver = None
        self._initialized = False
    
    def _get_neo4j_driver(self):
        """获取 Neo4j 驱动"""
        if not self.neo4j_driver:
            self.neo4j_driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
        return self.neo4j_driver
    
    async def initialize(self):
        """初始化服务"""
        if self._initialized:
            return
        
        try:
            driver = self._get_neo4j_driver()
            # 测试连接
            with driver.session() as session:
                session.run("RETURN 1")
            
            self._initialized = True
            logger.info("Value profiling service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize value profiling service: {e}")
            raise
    
    async def profile_column(
        self,
        connection_id: int,
        table_name: str,
        column_name: str,
        data_type: str
    ) -> ColumnProfile:
        """
        对单个字段进行 Profile 分析
        
        Args:
            connection_id: 数据库连接ID
            table_name: 表名
            column_name: 字段名
            data_type: 数据类型
            
        Returns:
            字段 Profile 对象
        """
        await self.initialize()
        
        connection = get_db_connection_by_id(connection_id)
        if not connection:
            raise ValueError(f"Connection {connection_id} not found")
        
        engine = get_db_engine(connection)
        profile = ColumnProfile(
            column_name=column_name,
            table_name=table_name,
            data_type=data_type,
            profiled_at=datetime.now()
        )
        
        try:
            with engine.connect() as conn:
                # 1. 获取基础统计
                stats_query = f"""
                    SELECT 
                        COUNT(*) AS total_count,
                        COUNT(DISTINCT `{column_name}`) AS distinct_count,
                        SUM(CASE WHEN `{column_name}` IS NULL THEN 1 ELSE 0 END) AS null_count
                    FROM `{table_name}`
                    LIMIT {SAMPLE_LIMIT}
                """
                result = conn.execute(text(stats_query))
                row = result.fetchone()
                
                if row:
                    profile.total_count = row[0] or 0
                    profile.distinct_count = row[1] or 0
                    profile.null_count = row[2] or 0
                
                # 2. 判断是否为枚举字段
                if profile.distinct_count <= ENUM_THRESHOLD and profile.distinct_count > 0:
                    profile.is_enum = True
                    
                    # 获取枚举值
                    enum_query = f"""
                        SELECT DISTINCT `{column_name}` 
                        FROM `{table_name}` 
                        WHERE `{column_name}` IS NOT NULL
                        ORDER BY `{column_name}`
                        LIMIT {ENUM_THRESHOLD}
                    """
                    result = conn.execute(text(enum_query))
                    profile.enum_values = [str(row[0]) for row in result.fetchall()]
                
                # 3. 获取数值范围（数值类型字段）
                if self._is_numeric_type(data_type):
                    range_query = f"""
                        SELECT MIN(`{column_name}`), MAX(`{column_name}`)
                        FROM `{table_name}`
                    """
                    result = conn.execute(text(range_query))
                    row = result.fetchone()
                    if row:
                        profile.min_value = row[0]
                        profile.max_value = row[1]
                
                # 4. 获取日期范围（日期类型字段）
                if self._is_date_type(data_type):
                    date_query = f"""
                        SELECT MIN(`{column_name}`), MAX(`{column_name}`)
                        FROM `{table_name}`
                    """
                    result = conn.execute(text(date_query))
                    row = result.fetchone()
                    if row:
                        profile.date_min = str(row[0]) if row[0] else None
                        profile.date_max = str(row[1]) if row[1] else None
                
                # 5. 获取采样值
                sample_query = f"""
                    SELECT DISTINCT `{column_name}`
                    FROM `{table_name}`
                    WHERE `{column_name}` IS NOT NULL
                    LIMIT 10
                """
                result = conn.execute(text(sample_query))
                profile.sample_values = [row[0] for row in result.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to profile column {table_name}.{column_name}: {e}")
            # 返回基础 profile，不抛出异常
        
        # 存储到 Neo4j
        await self._store_profile_to_neo4j(connection_id, table_name, column_name, profile)
        
        return profile
    
    async def profile_table(
        self,
        connection_id: int,
        table_name: str
    ) -> TableProfile:
        """
        对整个表进行 Profile 分析
        
        Args:
            connection_id: 数据库连接ID
            table_name: 表名
            
        Returns:
            表 Profile 对象
        """
        await self.initialize()
        
        connection = get_db_connection_by_id(connection_id)
        if not connection:
            raise ValueError(f"Connection {connection_id} not found")
        
        engine = get_db_engine(connection)
        
        # 获取行数
        row_count = 0
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
                row = result.fetchone()
                row_count = row[0] if row else 0
        except Exception as e:
            logger.error(f"Failed to get row count for {table_name}: {e}")
        
        # 获取字段列表
        columns = await self._get_columns_from_neo4j(connection_id, table_name)
        
        # Profile 每个字段
        column_profiles = []
        for col in columns:
            try:
                profile = await self.profile_column(
                    connection_id,
                    table_name,
                    col["name"],
                    col["type"]
                )
                column_profiles.append(profile)
            except Exception as e:
                logger.error(f"Failed to profile column {col['name']}: {e}")
        
        return TableProfile(
            table_name=table_name,
            connection_id=connection_id,
            row_count=row_count,
            columns=column_profiles,
            profiled_at=datetime.now()
        )
    
    async def profile_all_tables(self, connection_id: int) -> List[TableProfile]:
        """
        对连接的所有表进行 Profile 分析
        
        Args:
            connection_id: 数据库连接ID
            
        Returns:
            所有表的 Profile 列表
        """
        await self.initialize()
        
        # 获取所有表
        tables = await self._get_tables_from_neo4j(connection_id)
        
        profiles = []
        for table_name in tables:
            try:
                logger.info(f"Profiling table: {table_name}")
                profile = await self.profile_table(connection_id, table_name)
                profiles.append(profile)
            except Exception as e:
                logger.error(f"Failed to profile table {table_name}: {e}")
        
        logger.info(f"Completed profiling {len(profiles)} tables for connection {connection_id}")
        return profiles
    
    async def get_column_profile(
        self,
        connection_id: int,
        table_name: str,
        column_name: str
    ) -> Optional[ColumnProfile]:
        """
        从 Neo4j 获取已存储的字段 Profile
        
        Args:
            connection_id: 数据库连接ID
            table_name: 表名
            column_name: 字段名
            
        Returns:
            字段 Profile 对象
        """
        await self.initialize()
        
        driver = self._get_neo4j_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (t:Table {name: $table_name, connection_id: $connection_id})-[:HAS_COLUMN]->(c:Column {name: $column_name})
                RETURN c
            """, table_name=table_name, connection_id=connection_id, column_name=column_name)
            
            record = result.single()
            if not record:
                return None
            
            col = record["c"]
            
            # 检查是否有 profile 数据
            if not col.get("profiled_at"):
                return None
            
            return ColumnProfile(
                column_name=col["name"],
                table_name=table_name,
                data_type=col.get("type", "unknown"),
                distinct_count=col.get("distinct_count", 0),
                null_count=col.get("null_count", 0),
                total_count=col.get("total_count", 0),
                enum_values=col.get("enum_values", []),
                is_enum=col.get("is_enum", False),
                min_value=col.get("min_value"),
                max_value=col.get("max_value"),
                date_min=col.get("date_min"),
                date_max=col.get("date_max"),
                sample_values=col.get("sample_values", []),
                profiled_at=col.get("profiled_at")
            )
    
    async def get_enum_columns(
        self,
        connection_id: int,
        table_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取枚举类型字段及其值（用于 Schema Agent）
        
        Args:
            connection_id: 数据库连接ID
            table_name: 可选，指定表名
            
        Returns:
            枚举字段列表
        """
        await self.initialize()
        
        driver = self._get_neo4j_driver()
        with driver.session() as session:
            if table_name:
                result = session.run("""
                    MATCH (t:Table {name: $table_name, connection_id: $connection_id})-[:HAS_COLUMN]->(c:Column)
                    WHERE c.is_enum = true
                    RETURN t.name AS table_name, c.name AS column_name, c.enum_values AS enum_values
                """, table_name=table_name, connection_id=connection_id)
            else:
                result = session.run("""
                    MATCH (t:Table {connection_id: $connection_id})-[:HAS_COLUMN]->(c:Column)
                    WHERE c.is_enum = true
                    RETURN t.name AS table_name, c.name AS column_name, c.enum_values AS enum_values
                """, connection_id=connection_id)
            
            return [
                {
                    "table_name": record["table_name"],
                    "column_name": record["column_name"],
                    "enum_values": record["enum_values"] or []
                }
                for record in result
            ]
    
    async def get_date_columns(
        self,
        connection_id: int,
        table_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取日期字段及其范围（用于 Schema Agent）
        
        Args:
            connection_id: 数据库连接ID
            table_name: 可选，指定表名
            
        Returns:
            日期字段列表
        """
        await self.initialize()
        
        driver = self._get_neo4j_driver()
        with driver.session() as session:
            if table_name:
                result = session.run("""
                    MATCH (t:Table {name: $table_name, connection_id: $connection_id})-[:HAS_COLUMN]->(c:Column)
                    WHERE c.date_min IS NOT NULL OR c.date_max IS NOT NULL
                    RETURN t.name AS table_name, c.name AS column_name, 
                           c.date_min AS date_min, c.date_max AS date_max
                """, table_name=table_name, connection_id=connection_id)
            else:
                result = session.run("""
                    MATCH (t:Table {connection_id: $connection_id})-[:HAS_COLUMN]->(c:Column)
                    WHERE c.date_min IS NOT NULL OR c.date_max IS NOT NULL
                    RETURN t.name AS table_name, c.name AS column_name,
                           c.date_min AS date_min, c.date_max AS date_max
                """, connection_id=connection_id)
            
            return [
                {
                    "table_name": record["table_name"],
                    "column_name": record["column_name"],
                    "date_min": record["date_min"],
                    "date_max": record["date_max"]
                }
                for record in result
            ]
    
    # ===== 辅助方法 =====
    
    async def _store_profile_to_neo4j(
        self,
        connection_id: int,
        table_name: str,
        column_name: str,
        profile: ColumnProfile
    ):
        """将 Profile 结果存储到 Neo4j Column 节点"""
        driver = self._get_neo4j_driver()
        with driver.session() as session:
            session.run("""
                MATCH (t:Table {name: $table_name, connection_id: $connection_id})-[:HAS_COLUMN]->(c:Column {name: $column_name})
                SET c.distinct_count = $distinct_count,
                    c.null_count = $null_count,
                    c.total_count = $total_count,
                    c.enum_values = $enum_values,
                    c.is_enum = $is_enum,
                    c.min_value = $min_value,
                    c.max_value = $max_value,
                    c.date_min = $date_min,
                    c.date_max = $date_max,
                    c.sample_values = $sample_values,
                    c.profiled_at = datetime($profiled_at)
            """,
                table_name=table_name,
                connection_id=connection_id,
                column_name=column_name,
                distinct_count=profile.distinct_count,
                null_count=profile.null_count,
                total_count=profile.total_count,
                enum_values=profile.enum_values,
                is_enum=profile.is_enum,
                min_value=str(profile.min_value) if profile.min_value is not None else None,
                max_value=str(profile.max_value) if profile.max_value is not None else None,
                date_min=profile.date_min,
                date_max=profile.date_max,
                sample_values=[str(v) for v in profile.sample_values],
                profiled_at=profile.profiled_at.isoformat() if profile.profiled_at else datetime.now().isoformat()
            )
    
    async def _get_tables_from_neo4j(self, connection_id: int) -> List[str]:
        """从 Neo4j 获取表名列表"""
        driver = self._get_neo4j_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (t:Table {connection_id: $connection_id})
                RETURN t.name AS name
                ORDER BY t.name
            """, connection_id=connection_id)
            
            return [record["name"] for record in result]
    
    async def _get_columns_from_neo4j(
        self,
        connection_id: int,
        table_name: str
    ) -> List[Dict[str, str]]:
        """从 Neo4j 获取字段列表"""
        driver = self._get_neo4j_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (t:Table {name: $table_name, connection_id: $connection_id})-[:HAS_COLUMN]->(c:Column)
                RETURN c.name AS name, c.type AS type
                ORDER BY c.name
            """, table_name=table_name, connection_id=connection_id)
            
            return [{"name": record["name"], "type": record["type"] or "unknown"} for record in result]
    
    def _is_numeric_type(self, data_type: str) -> bool:
        """判断是否为数值类型"""
        numeric_types = [
            "int", "integer", "bigint", "smallint", "tinyint",
            "float", "double", "decimal", "numeric", "real",
            "number"
        ]
        return any(t in data_type.lower() for t in numeric_types)
    
    def _is_date_type(self, data_type: str) -> bool:
        """判断是否为日期类型"""
        date_types = ["date", "datetime", "timestamp", "time"]
        return any(t in data_type.lower() for t in date_types)
    
    def close(self):
        """关闭连接"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            self.neo4j_driver = None


# 创建全局实例
value_profiling_service = ValueProfilingService()
