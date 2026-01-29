"""
Schema 同步检索器
基于自然语言查询检索相关的表结构信息
"""

import time
import hashlib
import logging
from typing import Dict, Any

from sqlalchemy.orm import Session
from neo4j import GraphDatabase

from app.core.config import settings
from app import crud
from app.services.text2sql.cache import (
    full_schema_context_cache,
    full_schema_context_timestamps,
    get_cached_all_tables,
    FULL_SCHEMA_CONTEXT_CACHE_TTL,
)
from app.services.text2sql.analysis import (
    analyze_query_and_find_tables_unified,
    filter_expanded_tables_with_llm,
)


logger = logging.getLogger(__name__)


def retrieve_relevant_schema(db: Session, connection_id: int, query: str) -> Dict[str, Any]:
    """
    基于自然语言查询检索相关的表结构信息
    使用Neo4j图数据库和LLM找到相关表和列
    
    优化：
    - 使用统一的LLM调用，减少延迟
    - 添加完整 schema 上下文缓存（相同查询直接返回）
    - 跳过不必要的 LLM 过滤调用
    """
    # 检查完整 schema 上下文缓存
    query_normalized = query.strip().lower()
    cache_key = f"{connection_id}:{hashlib.md5(query_normalized.encode()).hexdigest()[:16]}"
    
    if cache_key in full_schema_context_cache:
        cache_time = full_schema_context_timestamps.get(cache_key, 0)
        if (time.time() - cache_time) < FULL_SCHEMA_CONTEXT_CACHE_TTL:
            logger.info(f"Schema 上下文缓存命中 (query: {query[:30]}...)")
            return full_schema_context_cache[cache_key]
    
    try:
        # 连接到Neo4j
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

        # 使用字典按ID跟踪表以防止重复
        relevant_tables_dict = {}
        relevant_columns = set()
        table_relevance_scores = {}

        with driver.session() as neo4j_session:
            # 1. 优化：使用缓存获取所有表（减少Neo4j查询）
            all_tables = get_cached_all_tables(connection_id, neo4j_session)

            # 2. 优化：使用统一函数同时完成查询分析和表匹配（单次LLM调用）
            query_analysis, relevant_table_ids = analyze_query_and_find_tables_unified(
                query, all_tables
            )

            # 3. 按ID获取表并设置相关性分数
            for table_id, relevance_score in relevant_table_ids:
                # 确保table_id是整数类型
                if not isinstance(table_id, int):
                    try:
                        table_id = int(table_id)
                    except (ValueError, TypeError):
                        continue

                # 查找表信息
                table_info = next((t for t in all_tables if t["id"] == table_id), None)
                if table_info:
                    # 在字典中存储表，以ID为键
                    relevant_tables_dict[table_info["id"]] = (
                        table_info["id"], table_info["name"], table_info["description"]
                    )
                    table_relevance_scores[table_info["id"]] = relevance_score

            # 4. 找到与查询相关的列
            for entity in query_analysis.get("entities", []):
                # 搜索匹配实体名称或描述的列
                result = neo4j_session.run(
                    """
                    MATCH (c:Column {connection_id: $connection_id})
                    WHERE toLower(c.name) CONTAINS $entity OR toLower(c.description) CONTAINS $entity
                    MATCH (t:Table)-[:HAS_COLUMN]->(c)
                    RETURN c.id AS id, c.name AS name, c.type AS type, c.description AS description,
                           c.is_pk AS is_pk, c.is_fk AS is_fk, t.id AS table_id, t.name AS table_name
                    """,
                    connection_id=connection_id,
                    entity=entity.lower()
                )

                for record in result:
                    relevant_columns.add((
                        record["id"], record["name"], record["type"], record["description"],
                        record["is_pk"], record["is_fk"], record["table_id"], record["table_name"]
                    ))
                    # 添加表或更新（如果已存在且有更好的描述）
                    if record["table_id"] not in relevant_tables_dict or not relevant_tables_dict[record["table_id"]][2]:
                        relevant_tables_dict[record["table_id"]] = (
                            record["table_id"], record["table_name"], ""
                        )
                    # 为有匹配列的表增加相关性分数
                    table_relevance_scores[record["table_id"]] = table_relevance_scores.get(record["table_id"], 0) + 0.5

            # 5. 如果找到了一些相关表/列，扩展以包含相关表
            if relevant_tables_dict or relevant_columns:
                table_ids = list(relevant_tables_dict.keys())

                # 通过外键找到连接的表（1跳）
                if table_ids:
                    result = neo4j_session.run(
                        """
                        MATCH (t1:Table {connection_id: $connection_id})-[:HAS_COLUMN]->
                              (c1:Column)-[:REFERENCES]->
                              (c2:Column)<-[:HAS_COLUMN]-(t2:Table {connection_id: $connection_id})
                        WHERE t1.id IN $table_ids AND NOT t2.id IN $table_ids
                        RETURN t2.id AS id, t2.name AS name, t2.description AS description,
                               c1.id AS source_column_id, c1.name AS source_column_name,
                               c2.id AS target_column_id, c2.name AS target_column_name,
                               t1.id AS source_table_id
                        """,
                        connection_id=connection_id,
                        table_ids=table_ids
                    )

                    for record in result:
                        # 添加表或更新（如果已存在且有更好的描述）
                        if record["id"] not in relevant_tables_dict or (
                            not relevant_tables_dict[record["id"]][2] and record["description"]
                        ):
                            relevant_tables_dict[record["id"]] = (
                                record["id"], record["name"], record["description"]
                            )
                        # 相关表基于源表的分数获得相关性分数
                        source_score = table_relevance_scores.get(record["source_table_id"], 0)
                        table_relevance_scores[record["id"]] = source_score * 0.7  # 相关表分数降低

                # 6. 优化：只对较多扩展表使用LLM过滤（减少不必要的LLM调用）
                # 阈值从3提高到6，减少LLM调用频率
                expanded_tables = [t for t in relevant_tables_dict.values() if t[0] not in table_ids]
                if expanded_tables and len(expanded_tables) > 6:
                    # 只有当扩展表超过6个时才调用LLM过滤
                    logger.info(f"扩展表数量({len(expanded_tables)}) > 6，调用LLM过滤")
                    filtered_expanded_tables = filter_expanded_tables_with_llm(
                        query, query_analysis, expanded_tables, table_relevance_scores
                    )
                    # 移除LLM认为不相关的表
                    filtered_table_ids = set(table_ids).union({t[0] for t in filtered_expanded_tables})
                    relevant_tables_dict = {
                        tid: t for tid, t in relevant_tables_dict.items() if tid in filtered_table_ids
                    }
                elif expanded_tables:
                    # 扩展表 <= 6 个时，使用简单的分数过滤代替LLM
                    logger.info(f"扩展表数量({len(expanded_tables)}) <= 6，使用分数过滤跳过LLM")
                    # 只保留分数 > 0.3 的扩展表
                    high_score_expanded = [t for t in expanded_tables if table_relevance_scores.get(t[0], 0) > 0.3]
                    if high_score_expanded:
                        filtered_table_ids = set(table_ids).union({t[0] for t in high_score_expanded})
                        relevant_tables_dict = {
                            tid: t for tid, t in relevant_tables_dict.items() if tid in filtered_table_ids
                        }

        driver.close()

        # 8. 按相关性分数排序表
        sorted_tables = sorted(
            relevant_tables_dict.values(),
            key=lambda t: table_relevance_scores.get(t[0], 0),
            reverse=True
        )

        # 转换为字典列表
        tables_list = [{"id": t[0], "name": t[1], "description": t[2]} for t in sorted_tables]

        # 如果没有找到相关表，返回所有表
        if not tables_list:
            all_tables_from_db = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
            tables_list = [
                {
                    "id": table.id,
                    "name": table.table_name,
                    "description": table.description or ""
                }
                for table in all_tables_from_db
            ]

        columns_list = []

        # 获取表的所有列
        for table in tables_list:
            table_columns = crud.schema_column.get_by_table(db=db, table_id=table["id"])
            for column in table_columns:
                columns_list.append({
                    "id": column.id,
                    "name": column.column_name,
                    "type": column.data_type,
                    "description": column.description,
                    "is_primary_key": column.is_primary_key,
                    "is_foreign_key": column.is_foreign_key,
                    "table_id": table["id"],
                    "table_name": table["name"]
                })

        # 获取表之间的关系
        relationships_list = []
        table_ids = [t["id"] for t in tables_list]

        # 如果返回所有表，则获取所有关系
        all_tables_count = len(crud.schema_table.get_by_connection(db=db, connection_id=connection_id))
        if len(tables_list) == all_tables_count:
            all_relationships = crud.schema_relationship.get_by_connection(db=db, connection_id=connection_id)

            for rel in all_relationships:
                source_table = next((t for t in tables_list if t["id"] == rel.source_table_id), None)
                target_table = next((t for t in tables_list if t["id"] == rel.target_table_id), None)
                source_column = next((c for c in columns_list if c["id"] == rel.source_column_id), None)
                target_column = next((c for c in columns_list if c["id"] == rel.target_column_id), None)

                if source_table and target_table and source_column and target_column:
                    relationships_list.append({
                        "id": rel.id,
                        "source_table": source_table["name"],
                        "source_column": source_column["name"],
                        "target_table": target_table["name"],
                        "target_column": target_column["name"],
                        "relationship_type": rel.relationship_type
                    })
        else:
            # 如果只返回相关表，则获取这些表之间的关系
            for table in tables_list:
                source_rels = crud.schema_relationship.get_by_source_table(db=db, source_table_id=table["id"])
                target_rels = crud.schema_relationship.get_by_target_table(db=db, target_table_id=table["id"])

                for rel in source_rels + target_rels:
                    # 只包含相关表集中的表之间的关系
                    if rel.source_table_id in table_ids and rel.target_table_id in table_ids:
                        source_table = next((t for t in tables_list if t["id"] == rel.source_table_id), None)
                        target_table = next((t for t in tables_list if t["id"] == rel.target_table_id), None)
                        source_column = next((c for c in columns_list if c["id"] == rel.source_column_id), None)
                        target_column = next((c for c in columns_list if c["id"] == rel.target_column_id), None)

                        if source_table and target_table and source_column and target_column:
                            # 确保不重复添加关系
                            rel_dict = {
                                "id": rel.id,
                                "source_table": source_table["name"],
                                "source_column": source_column["name"],
                                "target_table": target_table["name"],
                                "target_column": target_column["name"],
                                "relationship_type": rel.relationship_type
                            }
                            if rel_dict not in relationships_list:
                                relationships_list.append(rel_dict)

        result = {
            "tables": tables_list,
            "columns": columns_list,
            "relationships": relationships_list
        }
        
        # 缓存完整 schema 上下文
        full_schema_context_cache[cache_key] = result
        full_schema_context_timestamps[cache_key] = time.time()
        logger.info(f"Schema 上下文已缓存 (tables: {len(tables_list)}, columns: {len(columns_list)})")
        
        return result
    except Exception as e:
        raise Exception(f"检索表结构上下文时出错: {str(e)}")
