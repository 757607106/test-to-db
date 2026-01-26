"""
指标库服务 (Metric Service)

管理 Neo4j 中的 Metric 节点，提供业务指标的 CRUD 操作。
这是语义层 (Semantic Layer) 的核心组件。

Neo4j 数据模型:
- Metric 节点：存储指标定义
- (Metric)-[:BELONGS_TO_TABLE]->(Table)：指标与表的关系
- (Metric)-[:USES_COLUMN]->(Column)：指标使用的字段
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import uuid

from neo4j import GraphDatabase

from app.core.config import settings
from app.schemas.metric import (
    MetricCreate, MetricUpdate, Metric, MetricWithContext,
    ColumnProfile, TableProfile
)

logger = logging.getLogger(__name__)


class MetricService:
    """指标库服务 - 管理 Neo4j 中的业务指标"""
    
    def __init__(self):
        self.driver = None
        self._initialized = False
    
    def _get_driver(self):
        """获取 Neo4j 驱动"""
        if not self.driver:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
        return self.driver
    
    async def initialize(self):
        """初始化服务并创建约束"""
        if self._initialized:
            return
        
        try:
            driver = self._get_driver()
            with driver.session() as session:
                # 创建 Metric 节点的唯一约束
                session.run("""
                    CREATE CONSTRAINT metric_id IF NOT EXISTS
                    FOR (m:Metric) REQUIRE m.id IS UNIQUE
                """)
                
                # 创建 Metric 名称 + connection_id 的唯一约束
                session.run("""
                    CREATE CONSTRAINT metric_name_connection IF NOT EXISTS
                    FOR (m:Metric) REQUIRE (m.name, m.connection_id) IS UNIQUE
                """)
                
                logger.info("Metric service initialized with Neo4j constraints")
            
            self._initialized = True
            
        except Exception as e:
            logger.warning(f"Failed to create Neo4j constraints (may already exist): {e}")
            self._initialized = True  # 继续运行，约束可能已存在
    
    # ===== CRUD 操作 =====
    
    async def create_metric(self, metric_data: MetricCreate) -> Metric:
        """
        创建指标
        
        Args:
            metric_data: 指标创建数据
            
        Returns:
            创建的指标对象
        """
        await self.initialize()
        
        metric_id = f"metric_{uuid.uuid4().hex[:12]}"
        now = datetime.now()
        
        driver = self._get_driver()
        with driver.session() as session:
            # 创建 Metric 节点
            result = session.run("""
                CREATE (m:Metric {
                    id: $id,
                    name: $name,
                    business_name: $business_name,
                    description: $description,
                    formula: $formula,
                    aggregation: $aggregation,
                    source_table: $source_table,
                    source_column: $source_column,
                    dimension_columns: $dimension_columns,
                    time_column: $time_column,
                    default_filters: $default_filters,
                    category: $category,
                    tags: $tags,
                    unit: $unit,
                    decimal_places: $decimal_places,
                    connection_id: $connection_id,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at)
                })
                RETURN m
            """,
                id=metric_id,
                name=metric_data.name,
                business_name=metric_data.business_name,
                description=metric_data.description,
                formula=metric_data.formula,
                aggregation=metric_data.aggregation,
                source_table=metric_data.source_table,
                source_column=metric_data.source_column,
                dimension_columns=metric_data.dimension_columns,
                time_column=metric_data.time_column,
                default_filters=str(metric_data.default_filters) if metric_data.default_filters else None,
                category=metric_data.category,
                tags=metric_data.tags,
                unit=metric_data.unit,
                decimal_places=metric_data.decimal_places,
                connection_id=metric_data.connection_id,
                created_at=now.isoformat(),
                updated_at=now.isoformat()
            )
            
            # 创建与 Table 的关系
            session.run("""
                MATCH (m:Metric {id: $metric_id})
                MATCH (t:Table {name: $table_name, connection_id: $connection_id})
                MERGE (m)-[:BELONGS_TO_TABLE]->(t)
            """,
                metric_id=metric_id,
                table_name=metric_data.source_table,
                connection_id=metric_data.connection_id
            )
            
            # 创建与 Column 的关系
            session.run("""
                MATCH (m:Metric {id: $metric_id})
                MATCH (t:Table {name: $table_name, connection_id: $connection_id})-[:HAS_COLUMN]->(c:Column {name: $column_name})
                MERGE (m)-[:USES_COLUMN]->(c)
            """,
                metric_id=metric_id,
                table_name=metric_data.source_table,
                column_name=metric_data.source_column,
                connection_id=metric_data.connection_id
            )
            
            logger.info(f"Created metric: {metric_data.name} (id: {metric_id})")
            
            return Metric(
                id=metric_id,
                name=metric_data.name,
                business_name=metric_data.business_name,
                description=metric_data.description,
                formula=metric_data.formula,
                aggregation=metric_data.aggregation,
                source_table=metric_data.source_table,
                source_column=metric_data.source_column,
                dimension_columns=metric_data.dimension_columns,
                time_column=metric_data.time_column,
                default_filters=metric_data.default_filters,
                category=metric_data.category,
                tags=metric_data.tags,
                unit=metric_data.unit,
                decimal_places=metric_data.decimal_places,
                connection_id=metric_data.connection_id,
                created_at=now,
                updated_at=now
            )
    
    async def get_metric(self, metric_id: str) -> Optional[Metric]:
        """
        获取单个指标
        
        Args:
            metric_id: 指标ID
            
        Returns:
            指标对象，不存在则返回 None
        """
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (m:Metric {id: $metric_id})
                RETURN m
            """, metric_id=metric_id)
            
            record = result.single()
            if not record:
                return None
            
            return self._build_metric_from_record(record["m"])
    
    async def get_metrics_by_connection(
        self,
        connection_id: int,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[Metric]:
        """
        获取指定连接的所有指标
        
        Args:
            connection_id: 数据库连接ID
            category: 可选，按分类筛选
            tags: 可选，按标签筛选
            
        Returns:
            指标列表
        """
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            # 构建查询
            query = "MATCH (m:Metric {connection_id: $connection_id})"
            params = {"connection_id": connection_id}
            
            if category:
                query += " WHERE m.category = $category"
                params["category"] = category
            
            if tags:
                if "WHERE" in query:
                    query += " AND ANY(tag IN $tags WHERE tag IN m.tags)"
                else:
                    query += " WHERE ANY(tag IN $tags WHERE tag IN m.tags)"
                params["tags"] = tags
            
            query += " RETURN m ORDER BY m.category, m.name"
            
            result = session.run(query, **params)
            
            metrics = []
            for record in result:
                metrics.append(self._build_metric_from_record(record["m"]))
            
            return metrics
    
    async def get_metric_by_name(
        self,
        name: str,
        connection_id: int
    ) -> Optional[Metric]:
        """
        根据名称获取指标（支持 name 或 business_name）
        
        Args:
            name: 指标名称或业务别名
            connection_id: 数据库连接ID
            
        Returns:
            指标对象
        """
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (m:Metric {connection_id: $connection_id})
                WHERE m.name = $name OR m.business_name = $name
                RETURN m
                LIMIT 1
            """, name=name, connection_id=connection_id)
            
            record = result.single()
            if not record:
                return None
            
            return self._build_metric_from_record(record["m"])
    
    async def search_metrics(
        self,
        query: str,
        connection_id: int,
        limit: int = 10
    ) -> List[MetricWithContext]:
        """
        搜索指标（支持名称、描述、标签模糊匹配）
        
        Args:
            query: 搜索关键词
            connection_id: 数据库连接ID
            limit: 返回数量限制
            
        Returns:
            匹配的指标列表（带上下文）
        """
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (m:Metric {connection_id: $connection_id})
                WHERE toLower(m.name) CONTAINS toLower($query)
                   OR toLower(m.business_name) CONTAINS toLower($query)
                   OR toLower(m.description) CONTAINS toLower($query)
                   OR ANY(tag IN m.tags WHERE toLower(tag) CONTAINS toLower($query))
                OPTIONAL MATCH (m)-[:BELONGS_TO_TABLE]->(t:Table)
                OPTIONAL MATCH (m)-[:USES_COLUMN]->(c:Column)
                RETURN m, t.description AS table_description, c.type AS column_type
                LIMIT $limit
            """, query=query, connection_id=connection_id, limit=limit)
            
            metrics = []
            for record in result:
                metric = self._build_metric_from_record(record["m"])
                metrics.append(MetricWithContext(
                    **metric.model_dump(),
                    table_description=record.get("table_description"),
                    column_type=record.get("column_type"),
                    related_metrics=[]
                ))
            
            return metrics
    
    async def update_metric(
        self,
        metric_id: str,
        update_data: MetricUpdate
    ) -> Optional[Metric]:
        """
        更新指标
        
        Args:
            metric_id: 指标ID
            update_data: 更新数据
            
        Returns:
            更新后的指标对象
        """
        await self.initialize()
        
        # 构建 SET 子句
        set_clauses = []
        params = {"metric_id": metric_id, "updated_at": datetime.now().isoformat()}
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                if field == "default_filters":
                    params[field] = str(value)
                else:
                    params[field] = value
                set_clauses.append(f"m.{field} = ${field}")
        
        if not set_clauses:
            return await self.get_metric(metric_id)
        
        set_clauses.append("m.updated_at = datetime($updated_at)")
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run(f"""
                MATCH (m:Metric {{id: $metric_id}})
                SET {', '.join(set_clauses)}
                RETURN m
            """, **params)
            
            record = result.single()
            if not record:
                return None
            
            logger.info(f"Updated metric: {metric_id}")
            return self._build_metric_from_record(record["m"])
    
    async def delete_metric(self, metric_id: str) -> bool:
        """
        删除指标
        
        Args:
            metric_id: 指标ID
            
        Returns:
            是否删除成功
        """
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (m:Metric {id: $metric_id})
                DETACH DELETE m
                RETURN count(m) AS deleted
            """, metric_id=metric_id)
            
            record = result.single()
            deleted = record["deleted"] > 0
            
            if deleted:
                logger.info(f"Deleted metric: {metric_id}")
            
            return deleted
    
    # ===== 语义层查询辅助 =====
    
    async def get_metrics_for_query(
        self,
        user_query: str,
        connection_id: int
    ) -> List[MetricWithContext]:
        """
        根据用户查询获取相关指标（用于 Schema Agent）
        
        这是语义层的核心功能：将用户的自然语言查询映射到业务指标。
        
        Args:
            user_query: 用户查询
            connection_id: 数据库连接ID
            
        Returns:
            相关指标列表
        """
        await self.initialize()
        
        # 从查询中提取关键词
        keywords = self._extract_keywords(user_query)
        
        driver = self._get_driver()
        with driver.session() as session:
            # 多维度匹配：名称、业务名称、描述、标签
            result = session.run("""
                MATCH (m:Metric {connection_id: $connection_id})
                WITH m, 
                     CASE 
                        WHEN ANY(kw IN $keywords WHERE toLower(m.name) CONTAINS toLower(kw)) THEN 3
                        WHEN ANY(kw IN $keywords WHERE toLower(m.business_name) CONTAINS toLower(kw)) THEN 3
                        WHEN ANY(kw IN $keywords WHERE toLower(m.description) CONTAINS toLower(kw)) THEN 2
                        WHEN ANY(kw IN $keywords WHERE ANY(tag IN m.tags WHERE toLower(tag) CONTAINS toLower(kw))) THEN 1
                        ELSE 0
                     END AS relevance_score
                WHERE relevance_score > 0
                OPTIONAL MATCH (m)-[:BELONGS_TO_TABLE]->(t:Table)
                OPTIONAL MATCH (m)-[:USES_COLUMN]->(c:Column)
                RETURN m, t.description AS table_description, c.type AS column_type, relevance_score
                ORDER BY relevance_score DESC
                LIMIT 5
            """, keywords=keywords, connection_id=connection_id)
            
            metrics = []
            for record in result:
                metric = self._build_metric_from_record(record["m"])
                metrics.append(MetricWithContext(
                    **metric.model_dump(),
                    table_description=record.get("table_description"),
                    column_type=record.get("column_type"),
                    related_metrics=[]
                ))
            
            return metrics
    
    async def generate_sql_from_metrics(
        self,
        metrics: List[str],
        dimensions: List[str],
        connection_id: int,
        filters: Optional[Dict[str, Any]] = None,
        time_range: Optional[Dict[str, str]] = None
    ) -> str:
        """
        根据指标和维度生成 SQL
        
        Args:
            metrics: 指标名称列表
            dimensions: 维度字段列表
            connection_id: 数据库连接ID
            filters: 过滤条件
            time_range: 时间范围
            
        Returns:
            生成的 SQL
        """
        await self.initialize()
        
        # 获取指标定义
        metric_defs = []
        for metric_name in metrics:
            metric = await self.get_metric_by_name(metric_name, connection_id)
            if metric:
                metric_defs.append(metric)
        
        if not metric_defs:
            raise ValueError(f"No metrics found for: {metrics}")
        
        # 确定来源表
        source_tables = list(set(m.source_table for m in metric_defs))
        if len(source_tables) > 1:
            # 多表场景需要 JOIN，这里简化处理，使用第一个表
            logger.warning(f"Multiple source tables detected: {source_tables}, using first one")
        
        main_table = source_tables[0]
        
        # 构建 SELECT 子句
        select_parts = []
        for dim in dimensions:
            select_parts.append(dim)
        
        for metric in metric_defs:
            alias = metric.name.replace(" ", "_").lower()
            select_parts.append(f"{metric.formula} AS {alias}")
        
        # 构建 WHERE 子句
        where_clauses = []
        
        if time_range and metric_defs[0].time_column:
            time_col = metric_defs[0].time_column
            if "start" in time_range:
                where_clauses.append(f"{time_col} >= '{time_range['start']}'")
            if "end" in time_range:
                where_clauses.append(f"{time_col} <= '{time_range['end']}'")
        
        if filters:
            for field, value in filters.items():
                if isinstance(value, list):
                    values_str = ", ".join(f"'{v}'" for v in value)
                    where_clauses.append(f"{field} IN ({values_str})")
                else:
                    where_clauses.append(f"{field} = '{value}'")
        
        # 构建 SQL
        sql = f"SELECT {', '.join(select_parts)}\nFROM {main_table}"
        
        if where_clauses:
            sql += f"\nWHERE {' AND '.join(where_clauses)}"
        
        if dimensions:
            sql += f"\nGROUP BY {', '.join(dimensions)}"
        
        return sql
    
    # ===== 辅助方法 =====
    
    def _build_metric_from_record(self, node: Dict[str, Any]) -> Metric:
        """从 Neo4j 记录构建 Metric 对象"""
        # 处理日期时间
        created_at = node.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        
        updated_at = node.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        elif hasattr(updated_at, "to_native"):
            updated_at = updated_at.to_native()
        
        # 处理 default_filters
        default_filters = node.get("default_filters")
        if isinstance(default_filters, str):
            import ast
            try:
                default_filters = ast.literal_eval(default_filters)
            except:
                default_filters = None
        
        return Metric(
            id=node["id"],
            name=node["name"],
            business_name=node.get("business_name"),
            description=node.get("description"),
            formula=node["formula"],
            aggregation=node.get("aggregation", "SUM"),
            source_table=node["source_table"],
            source_column=node["source_column"],
            dimension_columns=node.get("dimension_columns", []),
            time_column=node.get("time_column"),
            default_filters=default_filters,
            category=node.get("category"),
            tags=node.get("tags", []),
            unit=node.get("unit"),
            decimal_places=node.get("decimal_places", 2),
            connection_id=node["connection_id"],
            created_at=created_at,
            updated_at=updated_at
        )
    
    def _extract_keywords(self, query: str) -> List[str]:
        """从用户查询中提取关键词"""
        import re
        
        # 移除标点符号
        query = re.sub(r'[^\w\s]', ' ', query)
        
        # 分词
        words = query.split()
        
        # 过滤停用词
        stop_words = {
            "的", "是", "在", "有", "和", "了", "我", "要", "查", "看",
            "帮", "请", "能", "不", "这", "那", "什么", "怎么", "多少",
            "the", "a", "an", "is", "are", "what", "how", "many", "much"
        }
        
        keywords = [w for w in words if w.lower() not in stop_words and len(w) > 1]
        
        return keywords[:10]  # 最多 10 个关键词
    
    def close(self):
        """关闭 Neo4j 连接"""
        if self.driver:
            self.driver.close()
            self.driver = None


# 创建全局实例
metric_service = MetricService()
