"""
JOIN 规则服务 (Join Rule Service)

管理 Neo4j 中的 JoinRule 节点，提供表关联规则的 CRUD 操作。
这些规则用于帮助 LLM 生成更准确的 SQL JOIN 语句。

Neo4j 数据模型:
- JoinRule 节点：存储 JOIN 规则定义
- (JoinRule)-[:JOINS_LEFT]->(Table)：规则与左表的关系
- (JoinRule)-[:JOINS_RIGHT]->(Table)：规则与右表的关系
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import uuid

from neo4j import GraphDatabase

from app.core.config import settings
from app.schemas.join_rule import (
    JoinRuleCreate, JoinRuleUpdate, JoinRule, JoinRuleContext
)

logger = logging.getLogger(__name__)


class JoinRuleService:
    """JOIN规则服务"""
    
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
        """初始化服务"""
        if self._initialized:
            return
        
        try:
            driver = self._get_driver()
            with driver.session() as session:
                session.run("""
                    CREATE CONSTRAINT join_rule_id IF NOT EXISTS
                    FOR (j:JoinRule) REQUIRE j.id IS UNIQUE
                """)
                logger.info("JoinRule service initialized")
            self._initialized = True
        except Exception as e:
            logger.warning(f"Failed to create constraints: {e}")
            self._initialized = True
    
    # ===== CRUD 操作 =====
    
    async def create_rule(self, rule_data: JoinRuleCreate) -> JoinRule:
        """创建 JOIN 规则"""
        await self.initialize()
        
        rule_id = f"join_{uuid.uuid4().hex[:12]}"
        now = datetime.now()
        
        driver = self._get_driver()
        with driver.session() as session:
            session.run("""
                CREATE (j:JoinRule {
                    id: $id,
                    name: $name,
                    description: $description,
                    left_table: $left_table,
                    left_column: $left_column,
                    right_table: $right_table,
                    right_column: $right_column,
                    join_type: $join_type,
                    priority: $priority,
                    extra_conditions: $extra_conditions,
                    tags: $tags,
                    is_active: $is_active,
                    connection_id: $connection_id,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at),
                    usage_count: 0
                })
            """,
                id=rule_id,
                name=rule_data.name,
                description=rule_data.description,
                left_table=rule_data.left_table,
                left_column=rule_data.left_column,
                right_table=rule_data.right_table,
                right_column=rule_data.right_column,
                join_type=rule_data.join_type,
                priority=rule_data.priority,
                extra_conditions=rule_data.extra_conditions,
                tags=rule_data.tags,
                is_active=rule_data.is_active,
                connection_id=rule_data.connection_id,
                created_at=now.isoformat(),
                updated_at=now.isoformat()
            )
            
            # 创建与表的关系
            session.run("""
                MATCH (j:JoinRule {id: $rule_id})
                OPTIONAL MATCH (lt:Table {name: $left_table, connection_id: $connection_id})
                OPTIONAL MATCH (rt:Table {name: $right_table, connection_id: $connection_id})
                FOREACH (_ IN CASE WHEN lt IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (j)-[:JOINS_LEFT]->(lt)
                )
                FOREACH (_ IN CASE WHEN rt IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (j)-[:JOINS_RIGHT]->(rt)
                )
            """,
                rule_id=rule_id,
                left_table=rule_data.left_table,
                right_table=rule_data.right_table,
                connection_id=rule_data.connection_id
            )
            
            logger.info(f"Created JOIN rule: {rule_data.name}")
            
            return JoinRule(
                id=rule_id,
                name=rule_data.name,
                description=rule_data.description,
                left_table=rule_data.left_table,
                left_column=rule_data.left_column,
                right_table=rule_data.right_table,
                right_column=rule_data.right_column,
                join_type=rule_data.join_type,
                priority=rule_data.priority,
                extra_conditions=rule_data.extra_conditions,
                tags=rule_data.tags,
                is_active=rule_data.is_active,
                connection_id=rule_data.connection_id,
                created_at=now,
                updated_at=now,
                usage_count=0
            )
    
    async def get_rule(self, rule_id: str) -> Optional[JoinRule]:
        """获取单个规则"""
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (j:JoinRule {id: $rule_id})
                RETURN j
            """, rule_id=rule_id)
            
            record = result.single()
            if not record:
                return None
            
            return self._build_rule_from_record(record["j"])
    
    async def get_rules_by_connection(
        self,
        connection_id: int,
        is_active: Optional[bool] = None
    ) -> List[JoinRule]:
        """获取连接的所有规则"""
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            query = "MATCH (j:JoinRule {connection_id: $connection_id})"
            params = {"connection_id": connection_id}
            
            if is_active is not None:
                query += " WHERE j.is_active = $is_active"
                params["is_active"] = is_active
            
            query += " RETURN j ORDER BY j.priority DESC, j.name"
            
            result = session.run(query, **params)
            
            rules = []
            for record in result:
                rules.append(self._build_rule_from_record(record["j"]))
            
            return rules
    
    async def get_rules_for_tables(
        self,
        connection_id: int,
        table_names: List[str]
    ) -> List[JoinRuleContext]:
        """
        获取与指定表相关的 JOIN 规则（用于 LLM）
        
        这是关键方法：当 LLM 需要生成涉及多表的 SQL 时，
        调用此方法获取预定义的 JOIN 规则。
        """
        await self.initialize()
        
        if not table_names or len(table_names) < 2:
            return []
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (j:JoinRule {connection_id: $connection_id, is_active: true})
                WHERE j.left_table IN $tables AND j.right_table IN $tables
                RETURN j
                ORDER BY j.priority DESC
            """, connection_id=connection_id, tables=table_names)
            
            contexts = []
            for record in result:
                node = record["j"]
                rule = self._build_rule_from_record(node)
                
                # 构建 JOIN 子句
                join_clause = self._build_join_clause(rule)
                
                contexts.append(JoinRuleContext(
                    rule_id=rule.id,
                    join_clause=join_clause,
                    priority=rule.priority,
                    description=rule.description
                ))
            
            return contexts
    
    async def update_rule(
        self,
        rule_id: str,
        update_data: JoinRuleUpdate
    ) -> Optional[JoinRule]:
        """更新规则"""
        await self.initialize()
        
        set_clauses = []
        params = {"rule_id": rule_id, "updated_at": datetime.now().isoformat()}
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                params[field] = value
                set_clauses.append(f"j.{field} = ${field}")
        
        if not set_clauses:
            return await self.get_rule(rule_id)
        
        set_clauses.append("j.updated_at = datetime($updated_at)")
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run(f"""
                MATCH (j:JoinRule {{id: $rule_id}})
                SET {', '.join(set_clauses)}
                RETURN j
            """, **params)
            
            record = result.single()
            if not record:
                return None
            
            logger.info(f"Updated JOIN rule: {rule_id}")
            return self._build_rule_from_record(record["j"])
    
    async def delete_rule(self, rule_id: str) -> bool:
        """删除规则"""
        await self.initialize()
        
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run("""
                MATCH (j:JoinRule {id: $rule_id})
                DETACH DELETE j
                RETURN count(j) AS deleted
            """, rule_id=rule_id)
            
            record = result.single()
            deleted = record["deleted"] > 0
            
            if deleted:
                logger.info(f"Deleted JOIN rule: {rule_id}")
            
            return deleted
    
    async def increment_usage(self, rule_id: str):
        """增加使用计数"""
        driver = self._get_driver()
        with driver.session() as session:
            session.run("""
                MATCH (j:JoinRule {id: $rule_id})
                SET j.usage_count = j.usage_count + 1
            """, rule_id=rule_id)
    
    # ===== 辅助方法 =====
    
    def _build_join_clause(self, rule: JoinRule) -> str:
        """构建 JOIN 子句"""
        join_clause = f"{rule.join_type} JOIN {rule.right_table} ON {rule.left_table}.{rule.left_column} = {rule.right_table}.{rule.right_column}"
        
        if rule.extra_conditions:
            join_clause += f" {rule.extra_conditions}"
        
        return join_clause
    
    def _build_rule_from_record(self, node: Dict[str, Any]) -> JoinRule:
        """从 Neo4j 记录构建 JoinRule 对象"""
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
        
        return JoinRule(
            id=node["id"],
            name=node["name"],
            description=node.get("description"),
            left_table=node["left_table"],
            left_column=node["left_column"],
            right_table=node["right_table"],
            right_column=node["right_column"],
            join_type=node.get("join_type", "INNER"),
            priority=node.get("priority", 1),
            extra_conditions=node.get("extra_conditions"),
            tags=node.get("tags", []),
            is_active=node.get("is_active", True),
            connection_id=node["connection_id"],
            created_at=created_at,
            updated_at=updated_at,
            usage_count=node.get("usage_count", 0)
        )
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            self.driver = None


# 创建全局实例
join_rule_service = JoinRuleService()
