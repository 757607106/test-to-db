"""
扩展的 Neo4j 服务
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from neo4j import GraphDatabase

from app.core.config import settings
from ..models import QAPairWithContext, RetrievalResult
from ..utils import extract_tables_from_sql

logger = logging.getLogger(__name__)


class EnhancedNeo4jService:
    """扩展的Neo4j服务"""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.driver = None
        self._initialized = False

    async def initialize(self):
        """初始化Neo4j连接"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # 测试连接
            with self.driver.session() as session:
                session.run("RETURN 1")
            self._initialized = True
            logger.info("Neo4j service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j service: {str(e)}")
            raise

    async def store_qa_pair_with_context(self, qa_pair: QAPairWithContext,
                                       schema_context: Dict[str, Any]):
        """存储问答对及其完整上下文信息"""
        if not self._initialized:
            await self.initialize()

        with self.driver.session() as session:
            try:
                # 1. 创建QAPair节点
                session.run("""
                    CREATE (qa:QAPair {
                        id: $id,
                        question: $question,
                        sql: $sql,
                        connection_id: $connection_id,
                        difficulty_level: $difficulty_level,
                        query_type: $query_type,
                        success_rate: $success_rate,
                        verified: $verified,
                        created_at: datetime($created_at)
                    })
                """,
                    id=qa_pair.id,
                    question=qa_pair.question,
                    sql=qa_pair.sql,
                    connection_id=qa_pair.connection_id,
                    difficulty_level=qa_pair.difficulty_level,
                    query_type=qa_pair.query_type,
                    success_rate=qa_pair.success_rate,
                    verified=qa_pair.verified,
                    created_at=qa_pair.created_at.isoformat()
                )

                # 2. 建立与Table的USES_TABLES关系
                # 如果used_tables为空，尝试从SQL中提取
                tables_to_use = qa_pair.used_tables
                if not tables_to_use and qa_pair.sql:
                    tables_to_use = extract_tables_from_sql(qa_pair.sql)
                    logger.info(f"从SQL中提取表名: {tables_to_use} for QA {qa_pair.id}")

                for table_name in tables_to_use:
                    # 检查表是否存在
                    table_exists = session.run("""
                        MATCH (t:Table {name: $table_name, connection_id: $connection_id})
                        RETURN count(t) > 0 as exists
                    """, table_name=table_name, connection_id=qa_pair.connection_id).single()['exists']

                    if table_exists:
                        session.run("""
                            MATCH (qa:QAPair {id: $qa_id})
                            MATCH (t:Table {name: $table_name, connection_id: $connection_id})
                            CREATE (qa)-[:USES_TABLES]->(t)
                        """, qa_id=qa_pair.id, table_name=table_name,
                            connection_id=qa_pair.connection_id)
                    else:
                        logger.warning(f"表 {table_name} 在连接 {qa_pair.connection_id} 中不存在")

                # 3. 创建或更新QueryPattern
                await self._create_or_update_pattern(session, qa_pair)

                # 4. 创建Entity节点和关系
                await self._create_entity_relationships(session, qa_pair)

                logger.info(f"Stored QA pair with context: {qa_pair.id}")

            except Exception as e:
                logger.error(f"Failed to store QA pair with context: {str(e)}")
                raise

    async def _create_or_update_pattern(self, session, qa_pair: QAPairWithContext):
        """创建或更新查询模式"""
        pattern_id = f"pattern_{qa_pair.query_type}_{qa_pair.difficulty_level}"

        # 检查模式是否存在
        result = session.run("""
            MATCH (p:QueryPattern {id: $pattern_id})
            RETURN p
        """, pattern_id=pattern_id)

        if result.single():
            # 更新使用计数
            session.run("""
                MATCH (p:QueryPattern {id: $pattern_id})
                SET p.usage_count = p.usage_count + 1
            """, pattern_id=pattern_id)
        else:
            # 创建新模式
            session.run("""
                CREATE (p:QueryPattern {
                    id: $pattern_id,
                    name: $query_type,
                    difficulty_level: $difficulty_level,
                    usage_count: 1,
                    created_at: datetime()
                })
            """,
                pattern_id=pattern_id,
                query_type=qa_pair.query_type,
                difficulty_level=qa_pair.difficulty_level
            )

        # 建立QAPair与Pattern的关系
        session.run("""
            MATCH (qa:QAPair {id: $qa_id})
            MATCH (p:QueryPattern {id: $pattern_id})
            CREATE (qa)-[:FOLLOWS_PATTERN]->(p)
        """, qa_id=qa_pair.id, pattern_id=pattern_id)

    async def _create_entity_relationships(self, session, qa_pair: QAPairWithContext):
        """创建实体关系"""
        for entity in qa_pair.mentioned_entities:
            entity_id = f"entity_{entity.lower().replace(' ', '_')}"

            # 创建或获取Entity节点
            session.run("""
                MERGE (e:Entity {id: $entity_id})
                ON CREATE SET e.name = $entity_name, e.created_at = datetime()
            """, entity_id=entity_id, entity_name=entity)

            # 建立关系
            session.run("""
                MATCH (qa:QAPair {id: $qa_id})
                MATCH (e:Entity {id: $entity_id})
                CREATE (qa)-[:MENTIONS_ENTITY]->(e)
            """, qa_id=qa_pair.id, entity_id=entity_id)

    async def structural_search(self, schema_context: Dict[str, Any],
                              connection_id: int, top_k: int = 20) -> List[RetrievalResult]:
        """基于schema结构的检索"""
        if not self._initialized:
            await self.initialize()

        table_names = [table.get('name') for table in schema_context.get('tables', [])]

        with self.driver.session() as session:
            result = session.run("""
                MATCH (qa:QAPair)-[:USES_TABLES]->(t:Table)
                WHERE t.name IN $table_names AND qa.connection_id = $connection_id
                WITH qa, count(t) as table_overlap, collect(t.name) as used_tables
                ORDER BY table_overlap DESC, qa.success_rate DESC
                LIMIT $top_k
                RETURN qa, table_overlap, used_tables
            """, table_names=table_names, connection_id=connection_id, top_k=top_k)

            results = []
            for record in result:
                qa_data = record['qa']
                table_overlap = record['table_overlap']
                used_tables = record['used_tables']

                # 计算结构相似性分数
                structural_score = table_overlap / max(len(table_names), 1)

                qa_pair = self._build_qa_pair_from_record(qa_data, used_tables)
                results.append(RetrievalResult(
                    qa_pair=qa_pair,
                    structural_score=structural_score,
                    explanation=f"使用了{table_overlap}个相同的表"
                ))

            return results

    async def pattern_search(self, query_type: str, difficulty_level: int,
                           connection_id: int, top_k: int = 20) -> List[RetrievalResult]:
        """基于查询模式的检索"""
        if not self._initialized:
            await self.initialize()

        with self.driver.session() as session:
            result = session.run("""
                MATCH (qa:QAPair)-[:FOLLOWS_PATTERN]->(p:QueryPattern)
                WHERE p.name = $query_type
                AND p.difficulty_level <= $difficulty_level + 1
                AND qa.connection_id = $connection_id
                RETURN qa, p.usage_count
                ORDER BY qa.success_rate DESC, p.usage_count DESC
                LIMIT $top_k
            """, query_type=query_type, difficulty_level=difficulty_level,
                connection_id=connection_id, top_k=top_k)

            results = []
            for record in result:
                qa_data = record['qa']
                usage_count = record['p.usage_count']

                # 计算模式匹配分数
                pattern_score = min(1.0, usage_count / 100.0)  # 归一化使用次数

                qa_pair = self._build_qa_pair_from_record(qa_data)
                results.append(RetrievalResult(
                    qa_pair=qa_pair,
                    pattern_score=pattern_score,
                    explanation=f"匹配查询模式，使用次数: {usage_count}"
                ))

            return results

    def _build_qa_pair_from_record(self, qa_data, used_tables=None) -> QAPairWithContext:
        """从Neo4j记录构建QAPair对象"""
        return QAPairWithContext(
            id=qa_data['id'],
            question=qa_data['question'],
            sql=qa_data['sql'],
            connection_id=qa_data['connection_id'],
            difficulty_level=qa_data['difficulty_level'],
            query_type=qa_data['query_type'],
            success_rate=qa_data['success_rate'],
            verified=qa_data['verified'],
            created_at=datetime.fromisoformat(qa_data['created_at']) if isinstance(qa_data['created_at'], str) else qa_data['created_at'],
            used_tables=used_tables or [],
            used_columns=[],
            query_pattern=qa_data['query_type'],
            mentioned_entities=[]
        )

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
