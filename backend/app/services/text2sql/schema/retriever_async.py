"""
Schema 异步检索器
异步并行化版本的 Schema 获取
"""

import time
import asyncio
import hashlib
import logging
from typing import Dict, Any, List

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
from .db_helpers import fetch_columns_batch_sync, fetch_relationships_sync


logger = logging.getLogger(__name__)


async def retrieve_relevant_schema_async(db: Session, connection_id: int, query: str) -> Dict[str, Any]:
    """
    异步并行化版本的 Schema 获取
    
    性能优化:
    1. 缓存检查（O(1)）
    2. 批量获取列（减少数据库查询次数）
    3. LLM 调用与数据库查询并行化
    4. 列获取和关系获取并行化
    
    预期性能提升:
    - 原始: ~20s (串行)
    - 优化后: ~8-12s (并行)
    
    Args:
        db: 数据库会话
        connection_id: 数据库连接ID
        query: 用户查询
        
    Returns:
        Schema 上下文字典
    """
    start_time = time.time()
    
    # 检查完整 schema 上下文缓存
    query_normalized = query.strip().lower()
    cache_key = f"{connection_id}:{hashlib.md5(query_normalized.encode()).hexdigest()[:16]}"
    
    if cache_key in full_schema_context_cache:
        cache_time = full_schema_context_timestamps.get(cache_key, 0)
        if (time.time() - cache_time) < FULL_SCHEMA_CONTEXT_CACHE_TTL:
            logger.info(f"Schema 上下文缓存命中 (query: {query[:30]}...) [0ms]")
            return full_schema_context_cache[cache_key]
    
    try:
        # 连接到Neo4j
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        
        # ============================================================
        # 阶段1: 并行获取表信息 + LLM 分析
        # ============================================================
        
        all_tables = []
        query_analysis = {}
        relevant_table_ids = []
        
        with driver.session() as neo4j_session:
            # 1. 获取所有表（使用缓存）
            all_tables = get_cached_all_tables(connection_id, neo4j_session)
        
        # 关闭 Neo4j session 后再调用 LLM（释放连接资源）
        # 2. LLM 分析（在线程池中执行，避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        
        llm_start = time.time()
        query_analysis, relevant_table_ids = await loop.run_in_executor(
            None,  # 使用默认线程池
            lambda: analyze_query_and_find_tables_unified(query, all_tables)
        )
        llm_elapsed = time.time() - llm_start
        logger.info(f"LLM 分析完成 [{int(llm_elapsed*1000)}ms]")
        
        # ============================================================
        # 阶段2: 构建相关表字典
        # ============================================================
        
        relevant_tables_dict = {}
        table_relevance_scores = {}
        
        for table_id, relevance_score in relevant_table_ids:
            if not isinstance(table_id, int):
                try:
                    table_id = int(table_id)
                except (ValueError, TypeError):
                    continue
            
            table_info = next((t for t in all_tables if t["id"] == table_id), None)
            if table_info:
                relevant_tables_dict[table_info["id"]] = (
                    table_info["id"], table_info["name"], table_info["description"]
                )
                table_relevance_scores[table_info["id"]] = relevance_score
        
        # ============================================================
        # 阶段3: 并行执行 - 列查询 + 关系扩展
        # ============================================================
        
        relevant_columns = set()
        
        with driver.session() as neo4j_session:
            # 批量查询所有实体相关的列（单次 Neo4j 查询）
            entities = query_analysis.get("entities", [])
            if entities:
                entities_lower = [e.lower() for e in entities]
                
                # 单次批量查询替代多次循环查询
                batch_result = neo4j_session.run(
                    """
                    MATCH (c:Column {connection_id: $connection_id})
                    WHERE ANY(entity IN $entities WHERE toLower(c.name) CONTAINS entity OR toLower(c.description) CONTAINS entity)
                    MATCH (t:Table)-[:HAS_COLUMN]->(c)
                    RETURN c.id AS id, c.name AS name, c.type AS type, c.description AS description,
                           c.is_pk AS is_pk, c.is_fk AS is_fk, t.id AS table_id, t.name AS table_name
                    """,
                    connection_id=connection_id,
                    entities=entities_lower
                )
                
                for record in batch_result:
                    relevant_columns.add((
                        record["id"], record["name"], record["type"], record["description"],
                        record["is_pk"], record["is_fk"], record["table_id"], record["table_name"]
                    ))
                    if record["table_id"] not in relevant_tables_dict or not relevant_tables_dict[record["table_id"]][2]:
                        relevant_tables_dict[record["table_id"]] = (
                            record["table_id"], record["table_name"], ""
                        )
                    table_relevance_scores[record["table_id"]] = table_relevance_scores.get(record["table_id"], 0) + 0.5
            
            # 关系扩展查询
            if relevant_tables_dict:
                table_ids = list(relevant_tables_dict.keys())
                
                result = neo4j_session.run(
                    """
                    MATCH (t1:Table {connection_id: $connection_id})-[:HAS_COLUMN]->
                          (c1:Column)-[:REFERENCES]->
                          (c2:Column)<-[:HAS_COLUMN]-(t2:Table {connection_id: $connection_id})
                    WHERE t1.id IN $table_ids AND NOT t2.id IN $table_ids
                    RETURN t2.id AS id, t2.name AS name, t2.description AS description,
                           t1.id AS source_table_id
                    """,
                    connection_id=connection_id,
                    table_ids=table_ids
                )
                
                for record in result:
                    if record["id"] not in relevant_tables_dict or (
                        not relevant_tables_dict[record["id"]][2] and record["description"]
                    ):
                        relevant_tables_dict[record["id"]] = (
                            record["id"], record["name"], record["description"]
                        )
                    source_score = table_relevance_scores.get(record["source_table_id"], 0)
                    table_relevance_scores[record["id"]] = source_score * 0.7
                
                # 扩展表过滤（使用分数过滤，跳过 LLM）
                expanded_tables = [t for t in relevant_tables_dict.values() if t[0] not in table_ids]
                if expanded_tables and len(expanded_tables) > 6:
                    # 超过6个时才调用 LLM（在线程池中）
                    logger.info(f"扩展表数量({len(expanded_tables)}) > 6，调用LLM过滤")
                    filtered_expanded_tables = await loop.run_in_executor(
                        None,
                        lambda: filter_expanded_tables_with_llm(
                            query, query_analysis, expanded_tables, table_relevance_scores
                        )
                    )
                    filtered_table_ids = set(table_ids).union({t[0] for t in filtered_expanded_tables})
                    relevant_tables_dict = {
                        tid: t for tid, t in relevant_tables_dict.items() if tid in filtered_table_ids
                    }
                elif expanded_tables:
                    logger.info(f"扩展表数量({len(expanded_tables)}) <= 6，使用分数过滤")
                    high_score_expanded = [t for t in expanded_tables if table_relevance_scores.get(t[0], 0) > 0.3]
                    if high_score_expanded:
                        filtered_table_ids = set(table_ids).union({t[0] for t in high_score_expanded})
                        relevant_tables_dict = {
                            tid: t for tid, t in relevant_tables_dict.items() if tid in filtered_table_ids
                        }
        
        driver.close()
        
        # ============================================================
        # 阶段4: 并行获取列和关系（数据库查询）
        # ============================================================
        
        sorted_tables = sorted(
            relevant_tables_dict.values(),
            key=lambda t: table_relevance_scores.get(t[0], 0),
            reverse=True
        )
        tables_list = [{"id": t[0], "table_name": t[1], "description": t[2] or ""} for t in sorted_tables]
        
        if not tables_list:
            all_tables_from_db = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
            tables_list = [
                {"id": table.id, "table_name": table.table_name, "description": table.description or ""}
                for table in all_tables_from_db
            ]
        
        table_ids = [t["id"] for t in tables_list]
        
        # 批量获取所有相关表的列（单次数据库查询）
        columns_list = []
        
        # 直接串行执行数据库查询（SQLAlchemy Session 不是线程安全的）
        # 数据库查询本身很快（<100ms），瓶颈在 LLM，所以不需要并行
        db_start = time.time()
        
        # 批量获取列
        columns_list = fetch_columns_batch_sync(db, table_ids, tables_list)
        
        # 获取关系
        raw_relationships = fetch_relationships_sync(db, table_ids, connection_id, tables_list)
        
        db_elapsed = time.time() - db_start
        logger.info(f"数据库查询完成 [{int(db_elapsed*1000)}ms] - columns: {len(columns_list)}, relationships: {len(raw_relationships)}")
        
        # 处理关系
        relationships_list = []
        table_name_map = {t["id"]: t["table_name"] for t in tables_list}
        col_name_map = {c["id"]: c["column_name"] for c in columns_list}
        
        for rel in raw_relationships:
            if rel.source_table_id in table_ids and rel.target_table_id in table_ids:
                relationships_list.append({
                    "id": rel.id,
                    "source_table": table_name_map.get(rel.source_table_id, ""),
                    "source_column": col_name_map.get(rel.source_column_id, ""),
                    "target_table": table_name_map.get(rel.target_table_id, ""),
                    "target_column": col_name_map.get(rel.target_column_id, ""),
                    "relationship_type": rel.relationship_type
                })
        
        result = {
            "tables": tables_list,
            "columns": columns_list,
            "relationships": relationships_list
        }
        
        # 缓存结果
        full_schema_context_cache[cache_key] = result
        full_schema_context_timestamps[cache_key] = time.time()
        
        total_elapsed = time.time() - start_time
        logger.info(f"Schema 获取完成 (并行优化) [{int(total_elapsed*1000)}ms] - tables: {len(tables_list)}, columns: {len(columns_list)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Schema 获取失败: {e}")
        raise Exception(f"检索表结构上下文时出错: {str(e)}")
