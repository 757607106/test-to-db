"""
Text2SQL工具模块
提供查询分析、表结构检索、SQL处理等工具函数

优化历史:
- 2026-01: 合并LLM调用，减少延迟
- 2026-01: 添加缓存优化
"""
import re
import json
import time
import logging
import sqlparse
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session
from neo4j import GraphDatabase

from app.core.config import settings
from app.core.llms import get_default_model
from app import crud


logger = logging.getLogger(__name__)


# ============================================================================
# 缓存配置（性能优化）
# ============================================================================

# 缓存TTL配置
QUERY_ANALYSIS_CACHE_TTL = 600  # 查询分析缓存: 10分钟
QUERY_ANALYSIS_CACHE_MAX_SIZE = 100  # 最大缓存条目数
SCHEMA_CACHE_TTL = 1800  # Schema缓存: 30分钟（表结构不常变）

# 查询分析缓存（带TTL和大小限制）
query_analysis_cache: Dict[str, Dict[str, Any]] = {}
query_analysis_cache_timestamps: Dict[str, float] = {}

# Schema缓存（按connection_id缓存表结构信息）
_schema_cache: Dict[int, Dict[str, Any]] = {}
_schema_cache_timestamps: Dict[int, float] = {}

# 完整 Schema 上下文缓存（按 connection_id + query_hash 缓存）
_full_schema_context_cache: Dict[str, Dict[str, Any]] = {}
_full_schema_context_timestamps: Dict[str, float] = {}
FULL_SCHEMA_CONTEXT_CACHE_TTL = 600  # 10分钟


def _is_query_cache_valid(query: str) -> bool:
    """检查查询缓存是否有效"""
    if query not in query_analysis_cache:
        return False
    cache_time = query_analysis_cache_timestamps.get(query, 0)
    return (time.time() - cache_time) < QUERY_ANALYSIS_CACHE_TTL


def _is_schema_cache_valid(connection_id: int) -> bool:
    """检查Schema缓存是否有效"""
    if connection_id not in _schema_cache:
        return False
    cache_time = _schema_cache_timestamps.get(connection_id, 0)
    return (time.time() - cache_time) < SCHEMA_CACHE_TTL


def _cleanup_query_cache():
    """清理过期和超出大小的缓存"""
    global query_analysis_cache, query_analysis_cache_timestamps
    
    current_time = time.time()
    
    # 移除过期条目
    expired_keys = [
        k for k, t in query_analysis_cache_timestamps.items()
        if (current_time - t) >= QUERY_ANALYSIS_CACHE_TTL
    ]
    for k in expired_keys:
        query_analysis_cache.pop(k, None)
        query_analysis_cache_timestamps.pop(k, None)
    
    # 如果仍超过大小限制，移除最旧的条目
    if len(query_analysis_cache) > QUERY_ANALYSIS_CACHE_MAX_SIZE:
        sorted_items = sorted(query_analysis_cache_timestamps.items(), key=lambda x: x[1])
        items_to_remove = len(query_analysis_cache) - QUERY_ANALYSIS_CACHE_MAX_SIZE
        for k, _ in sorted_items[:items_to_remove]:
            query_analysis_cache.pop(k, None)
            query_analysis_cache_timestamps.pop(k, None)


def get_cached_all_tables(connection_id: int, neo4j_session) -> List[Dict[str, Any]]:
    """
    获取缓存的所有表信息（优化Neo4j查询）
    
    Args:
        connection_id: 数据库连接ID
        neo4j_session: Neo4j会话
        
    Returns:
        表信息列表
    """
    cache_key = f"tables:{connection_id}"
    
    # 检查缓存
    if _is_schema_cache_valid(connection_id) and cache_key in _schema_cache:
        logger.debug(f"Using cached schema for connection {connection_id}")
        return _schema_cache[cache_key]
    
    # 从Neo4j查询
    all_tables = neo4j_session.run(
        """
        MATCH (t:Table {connection_id: $connection_id})
        RETURN t.id AS id, t.name AS name, t.description AS description
        """,
        connection_id=connection_id
    ).data()
    
    # 缓存结果
    _schema_cache[cache_key] = all_tables
    _schema_cache_timestamps[connection_id] = time.time()
    
    logger.debug(f"Cached {len(all_tables)} tables for connection {connection_id}")
    return all_tables


def clear_schema_cache(connection_id: Optional[int] = None):
    """
    清除Schema缓存
    
    Args:
        connection_id: 指定连接ID，如果为None则清除所有缓存
    """
    global _schema_cache, _schema_cache_timestamps
    
    if connection_id is not None:
        cache_key = f"tables:{connection_id}"
        _schema_cache.pop(cache_key, None)
        _schema_cache_timestamps.pop(connection_id, None)
        logger.info(f"Cleared schema cache for connection {connection_id}")
    else:
        _schema_cache.clear()
        _schema_cache_timestamps.clear()
        logger.info("Cleared all schema cache")


def analyze_query_with_llm(query: str) -> Dict[str, Any]:
    """
    使用LLM分析自然语言查询，提取关键实体和意图
    返回包含实体、关系和查询意图的结构化分析
    
    优化：使用带TTL的缓存
    """
    # 检查缓存（带TTL验证）
    if _is_query_cache_valid(query):
        logger.debug(f"Using cached query analysis: {query[:30]}...")
        return query_analysis_cache[query]
    
    try:
        # 为LLM准备提示
        prompt = f"""
        你是一名数据库专家，帮助分析自然语言查询以找到相关的数据库表和列。
        请分析以下查询并提取关键信息：

        查询: "{query}"

        请以以下JSON格式提供分析：
        {{
            "entities": [查询中提到或暗示的实体名称列表],
            "relationships": [查询中暗示的实体间关系列表],
            "query_intent": "查询试图找到什么的简要描述",
            "likely_aggregations": [可能需要的聚合操作列表，如count、sum、avg],
            "time_related": 布尔值，表示查询是否涉及时间/日期过滤或分组,
            "comparison_related": 布尔值，表示查询是否涉及值比较
        }}
        """
        # 调用LLM
        model_client = get_default_model()
        response = model_client.invoke(
            [{"role": "user", "content": prompt}, {"role": "system", "content": "你是一名数据库专家，擅长根据自然语言分析相关的数据库表及列"}]
        )

        response_text = response.content

        # 提取并解析JSON响应
        json_match = re.search(r'\{[\s\S]*}', response_text)
        if json_match:
            json_str = json_match.group(0)
            analysis = json.loads(json_str)

            # 验证必需字段
            if not all(k in analysis for k in ["entities", "relationships", "query_intent"]):
                analysis = _create_fallback_analysis(query)
        else:
            analysis = _create_fallback_analysis(query)

        # 缓存结果（带时间戳）
        _cleanup_query_cache()  # 先清理过期缓存
        query_analysis_cache[query] = analysis
        query_analysis_cache_timestamps[query] = time.time()
        
        return analysis
    except Exception as e:
        # 如果发生任何错误，回退到关键词提取
        logger.warning(f"LLM query analysis failed: {e}, using fallback")
        analysis = _create_fallback_analysis(query)
        query_analysis_cache[query] = analysis
        query_analysis_cache_timestamps[query] = time.time()
        return analysis


def analyze_query_and_find_tables_unified(
    query: str, 
    all_tables: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], List[Tuple[int, float]]]:
    """
    统一的查询分析和表匹配函数 - 合并为一次LLM调用
    
    优化：将原来的两次LLM调用合并为一次，大幅减少延迟
    
    Args:
        query: 用户自然语言查询
        all_tables: 所有可用表的列表
        
    Returns:
        Tuple[查询分析结果, 相关表列表(table_id, score)]
    """
    # 检查缓存
    cache_key = f"{query}:{hash(str(all_tables))}"
    if _is_query_cache_valid(cache_key):
        cached = query_analysis_cache[cache_key]
        return cached.get("analysis", {}), cached.get("tables", [])
    
    # 准备表信息
    tables_info = "\n".join([
        f"表ID: {t['id']} - 名称: {t['name']} - 描述: {t['description'] or '无描述'}"
        for t in all_tables
    ])
    
    # 统一提示词 - 一次完成分析和表匹配
    unified_prompt = f"""你是一名数据库专家。请同时完成以下两个任务：

**任务1: 分析查询**
分析用户的自然语言查询，提取关键实体和意图。

**任务2: 匹配相关表**
从可用表中找出与查询相关的表，并按相关性评分。

---
用户查询: "{query}"

可用表:
{tables_info}
---

请以JSON格式返回（必须同时包含analysis和relevant_tables两部分）:
{{
    "analysis": {{
        "entities": ["实体1", "实体2"],
        "relationships": ["关系描述"],
        "query_intent": "查询意图描述",
        "likely_aggregations": ["count", "sum"],
        "time_related": false,
        "comparison_related": false
    }},
    "relevant_tables": [
        {{
            "table_id": 123,
            "relevance_score": 8.5,
            "reasoning": "相关原因"
        }}
    ]
}}

注意：
- relevant_tables 中只包含相关性分数>3的表
- table_id 必须是整数
- relevance_score 范围是0-10
只返回JSON，不要其他内容。"""

    try:
        model_client = get_default_model()
        response = model_client.invoke(
            [{"role": "user", "content": unified_prompt},
             {"role": "system", "content": "你是一名数据库专家，擅长分析自然语言查询并匹配相关数据库表"}]
        )
        
        response_text = response.content
        
        # 解析JSON
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            result = json.loads(json_match.group(0))
            
            analysis = result.get("analysis", _create_fallback_analysis(query))
            
            # 处理表匹配结果
            relevant_tables = []
            for t in result.get("relevant_tables", []):
                if "table_id" in t and "relevance_score" in t:
                    if t["relevance_score"] > 3:
                        table_id = t["table_id"]
                        if not isinstance(table_id, int):
                            try:
                                table_id = int(table_id)
                            except (ValueError, TypeError):
                                continue
                        relevant_tables.append((table_id, t["relevance_score"]))
            
            # 如果没有找到相关表，使用基本匹配
            if not relevant_tables:
                relevant_tables = basic_table_matching(query, all_tables)
            
            # 缓存结果
            _cleanup_query_cache()
            query_analysis_cache[cache_key] = {
                "analysis": analysis,
                "tables": relevant_tables
            }
            query_analysis_cache_timestamps[cache_key] = time.time()
            
            # 同时更新简单查询缓存
            query_analysis_cache[query] = analysis
            query_analysis_cache_timestamps[query] = time.time()
            
            logger.info(f"Unified analysis found {len(relevant_tables)} relevant tables")
            return analysis, relevant_tables
        else:
            raise ValueError("Failed to parse LLM response")
            
    except Exception as e:
        logger.warning(f"Unified analysis failed: {e}, using fallback")
        analysis = _create_fallback_analysis(query)
        relevant_tables = basic_table_matching(query, all_tables)
        return analysis, relevant_tables


def _create_fallback_analysis(query: str) -> Dict[str, Any]:
    """创建回退分析结果"""
    return {
        "entities": extract_keywords(query),
        "relationships": [],
        "query_intent": query,
        "likely_aggregations": [],
        "time_related": False,
        "comparison_related": False
    }


def extract_keywords(query: str) -> List[str]:
    """
    使用正则表达式从查询中提取关键词（回退方法）
    """
    keywords = re.findall(r'\b\w+\b', query.lower())
    return [k for k in keywords if len(k) > 2 and k not in {
        'the', 'and', 'for', 'from', 'where', 'what', 'which', 'when', 'who',
        'how', 'many', 'much', 'with', 'that', 'this', 'these', 'those',
        '什么', '哪个', '哪些', '什么时候', '谁', '怎么', '多少', '和', '的', '是'
    }]


def find_relevant_tables_semantic(query: str, query_analysis: Dict[str, Any],
                                       all_tables: List[Dict[str, Any]]) -> List[Tuple[int, float]]:
    """
    使用LLM进行语义匹配找到相关表
    返回(table_id, relevance_score)元组列表
    """
    try:
        # 为LLM准备表信息
        tables_info = "\n".join([
            f"表ID: {t['id']} - 名称: {t['name']} - 描述: {t['description'] or '无描述'}"
            for t in all_tables
        ])

        # 准备提示
        prompt = f"""
        你是一名数据库专家，帮助为自然语言查询找到相关表。

        查询: "{query}"

        查询分析: {json.dumps(query_analysis, ensure_ascii=False)}

        可用表:
        {tables_info}

        请按相关性对表进行排序，返回包含table_id和relevance_score(0-10)的JSON数组。
        table_id必须是每个表描述开头显示的整数ID（例如"表ID: 123"）。
        只包含实际相关的表（分数>3）。格式：
        [
            {{
                "table_id": 123, // 表的整数ID，不是名称
                "relevance_score": 8.5, // 0-10之间的浮点数
                "reasoning": "为什么这个表相关的简要解释"
            }},
            ...
        ]
        """

        # 调用LLM
        model_client = get_default_model()
        # 直接使用model_client以保持一致性
        response = model_client.invoke(
            [{"role": "user", "content": prompt},
             {"role": "system", "content": "你是一名数据库专家，擅长根据自然语言分析相关的数据库表及列"}]
        )
        response_text = response.content
        # 提取并解析JSON响应
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            json_str = json_match.group(0)
            ranked_tables = json.loads(json_str)

            # 确保每个表都有所需字段且table_id是整数
            valid_tables = []
            for t in ranked_tables:
                if "table_id" in t and "relevance_score" in t:
                    if t["relevance_score"] > 3:
                        table_id = t["table_id"]
                        if not isinstance(table_id, int):
                            try:
                                table_id = int(table_id)
                            except (ValueError, TypeError):
                                continue
                        valid_tables.append((table_id, t["relevance_score"]))

            return valid_tables
        else:
            return basic_table_matching(query, all_tables)
    except Exception as e:
        return basic_table_matching(query, all_tables)


def basic_table_matching(query: str, all_tables: List[Dict[str, Any]]) -> List[Tuple[int, float]]:
    """
    基本关键词匹配回退方法
    """
    keywords = extract_keywords(query)
    relevant_tables = []

    for table in all_tables:
        score = 0
        table_name = table["name"].lower()
        table_desc = (table["description"] or "").lower()

        for keyword in keywords:
            if keyword in table_name:
                score += 5  # 名称匹配更高分
            elif keyword in table_desc:
                score += 3  # 描述匹配较低分

        if score > 0:
            relevant_tables.append((table["id"], min(score, 10)))  # 最高10分

    return sorted(relevant_tables, key=lambda x: x[1], reverse=True)


def filter_expanded_tables_with_llm(query: str, query_analysis: Dict[str, Any],
                                        expanded_tables: List[Tuple[int, str, str]],
                                        relevance_scores: Dict[int, float]) -> Set[Tuple[int, str, str]]:
    """
    使用LLM根据实际相关性过滤扩展表
    """
    try:
        # 准备扩展表信息
        tables_info = "\n".join([
            f"表ID: {t[0]}, 名称: {t[1]}, 描述: {t[2] or '无描述'}, 分数: {relevance_scores.get(t[0], 0)}"
            for t in expanded_tables
        ])

        # 准备提示
        prompt = f"""
        你是一名数据库专家，帮助确定相关表是否真正与查询相关。

        查询: "{query}"

        查询分析: {json.dumps(query_analysis, ensure_ascii=False)}

        以下表是通过关系连接找到的，但我们需要确定它们是否真正相关：
        {tables_info}

        请返回实际与回答查询相关的表ID的JSON数组。
        只包含回答查询所需的表。格式：
        [
            {{
                "table_id": table_id,
                "include": true/false,
                "reasoning": "为什么应该包含或排除此表的简要解释"
            }},
            ...
        ]
        """

        # 调用LLM
        model_client = get_default_model()
        # 直接使用model_client以保持一致性
        response = model_client.invoke(
            [{"role": "user", "content": prompt},
             {"role": "system", "content": "你是一名数据库专家，擅长分析自然语言查询与相关的数据库表是否有关"}]
        )
        response_text = response.content

        # 提取并解析JSON响应
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            json_str = json_match.group(0)
            filtered_tables = json.loads(json_str)

            # 获取应包含的表的ID
            include_ids = [t["table_id"] for t in filtered_tables if t.get("include", False)]

            # 返回应包含的原始表元组
            return set(t for t in expanded_tables if t[0] in include_ids)
        else:
            # 如果解析失败，包含所有扩展表
            return set(expanded_tables)
    except Exception as e:
        # 如果发生任何错误，包含所有扩展表
        return set(expanded_tables)


def format_schema_for_prompt(schema_context: Dict[str, Any]) -> str:
    """
    将表结构上下文格式化为LLM提示的字符串
    """
    tables = schema_context["tables"]
    columns = schema_context["columns"]
    relationships = schema_context["relationships"]

    # 按表分组列
    columns_by_table = {}
    for column in columns:
        table_name = column["table_name"]
        if table_name not in columns_by_table:
            columns_by_table[table_name] = []
        columns_by_table[table_name].append(column)

    # 格式化表结构
    schema_str = ""

    for table in tables:
        table_name = table["name"]
        table_desc = f" ({table['description']})" if table["description"] else ""

        schema_str += f"-- 表: {table_name}{table_desc}\n"
        schema_str += "-- 列:\n"

        if table_name in columns_by_table:
            for column in columns_by_table[table_name]:
                col_name = column["name"]
                col_type = column["type"]
                col_desc = f" ({column['description']})" if column["description"] else ""
                pk_flag = " PK" if column["is_primary_key"] else ""
                fk_flag = " FK" if column["is_foreign_key"] else ""

                schema_str += f"--   {col_name} {col_type}{pk_flag}{fk_flag}{col_desc}\n"

        schema_str += "\n"

    if relationships:
        schema_str += "-- 关系:\n"
        for rel in relationships:
            rel_type = f" ({rel['relationship_type']})" if rel["relationship_type"] else ""
            schema_str += f"-- {rel['source_table']}.{rel['source_column']} -> {rel['target_table']}.{rel['target_column']}{rel_type}\n"

    return schema_str


def get_value_mappings(db: Session, schema_context: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    获取表结构上下文中列的值映射
    """
    mappings = {}

    for column in schema_context["columns"]:
        column_id = column["id"]
        column_mappings = crud.value_mapping.get_by_column(db=db, column_id=column_id)

        if column_mappings:
            table_col = f"{column['table_name']}.{column['name']}"
            mappings[table_col] = {m.nl_term: m.db_value for m in column_mappings}

    return mappings


def process_sql_with_value_mappings(sql: str, value_mappings: Dict[str, Dict[str, str]]) -> str:
    """
    处理SQL查询，将自然语言术语替换为数据库值
    """
    if not value_mappings:
        return sql

    # 这是一个简化的方法 - 更健壮的实现会使用适当的SQL解析器
    for column, mappings in value_mappings.items():
        table, col = column.split('.')

        # 查找类似"table.column = 'value'"或"column = 'value'"的模式
        for nl_term, db_value in mappings.items():
            # 尝试匹配带表名的模式
            pattern1 = rf"({table}\.{col}\s*=\s*['\"])({nl_term})(['\"])"
            sql = re.sub(pattern1, f"\\1{db_value}\\3", sql, flags=re.IGNORECASE)

            # 尝试匹配不带表名的模式
            pattern2 = rf"({col}\s*=\s*['\"])({nl_term})(['\"])"
            sql = re.sub(pattern2, f"\\1{db_value}\\3", sql, flags=re.IGNORECASE)

            # 也处理LIKE模式
            pattern3 = rf"({table}\.{col}\s+LIKE\s+['\"])%?({nl_term})%?(['\"])"
            sql = re.sub(pattern3, f"\\1%{db_value}%\\3", sql, flags=re.IGNORECASE)

            pattern4 = rf"({col}\s+LIKE\s+['\"])%?({nl_term})%?(['\"])"
            sql = re.sub(pattern4, f"\\1%{db_value}%\\3", sql, flags=re.IGNORECASE)

    return sql


def validate_sql(sql: str) -> bool:
    """
    验证SQL语法
    """
    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            return False

        # 检查是否是SELECT语句（为了安全）
        stmt = parsed[0]
        return stmt.get_type().upper() == 'SELECT'
    except Exception:
        return False


def extract_sql_from_llm_response(response: str) -> str:
    """
    从LLM响应中提取SQL查询
    """
    # 查找SQL代码块
    sql_match = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
    if sql_match:
        return sql_match.group(1).strip()

    # 查找任何代码块
    code_match = re.search(r'```(.*?)```', response, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()

    # 如果没有代码块，尝试找到类似SQL的内容
    lines = response.split('\n')
    sql_lines = []
    in_sql = False

    for line in lines:
        if line.strip().upper().startswith('SELECT'):
            in_sql = True

        if in_sql:
            sql_lines.append(line)

            if ';' in line:
                break

    if sql_lines:
        return '\n'.join(sql_lines)

    # 如果都失败了，返回整个响应
    return response


def retrieve_relevant_schema(db: Session, connection_id: int, query: str) -> Dict[str, Any]:
    """
    基于自然语言查询检索相关的表结构信息
    使用Neo4j图数据库和LLM找到相关表和列
    
    优化：
    - 使用统一的LLM调用，减少延迟
    - 添加完整 schema 上下文缓存（相同查询直接返回）
    - 跳过不必要的 LLM 过滤调用
    """
    import hashlib
    
    # ✅ 优化1: 检查完整 schema 上下文缓存
    query_normalized = query.strip().lower()
    cache_key = f"{connection_id}:{hashlib.md5(query_normalized.encode()).hexdigest()[:16]}"
    
    if cache_key in _full_schema_context_cache:
        cache_time = _full_schema_context_timestamps.get(cache_key, 0)
        if (time.time() - cache_time) < FULL_SCHEMA_CONTEXT_CACHE_TTL:
            logger.info(f"✓ Schema 上下文缓存命中 (query: {query[:30]}...)")
            return _full_schema_context_cache[cache_key]
    
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
                # ✅ 优化: 阈值从3提高到6，减少LLM调用频率
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
                    # ✅ 优化: 扩展表 <= 6 个时，使用简单的分数过滤代替LLM
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
        
        # ✅ 优化: 缓存完整 schema 上下文
        _full_schema_context_cache[cache_key] = result
        _full_schema_context_timestamps[cache_key] = time.time()
        logger.info(f"✓ Schema 上下文已缓存 (tables: {len(tables_list)}, columns: {len(columns_list)})")
        
        return result
    except Exception as e:
        raise Exception(f"检索表结构上下文时出错: {str(e)}")


# ============================================================================
# 并行化 Schema 获取 (性能优化版)
# ============================================================================

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
    import asyncio
    import hashlib
    import concurrent.futures
    
    start_time = time.time()
    
    # ✅ 优化1: 检查完整 schema 上下文缓存
    query_normalized = query.strip().lower()
    cache_key = f"{connection_id}:{hashlib.md5(query_normalized.encode()).hexdigest()[:16]}"
    
    if cache_key in _full_schema_context_cache:
        cache_time = _full_schema_context_timestamps.get(cache_key, 0)
        if (time.time() - cache_time) < FULL_SCHEMA_CONTEXT_CACHE_TTL:
            logger.info(f"✓ Schema 上下文缓存命中 (query: {query[:30]}...) [0ms]")
            return _full_schema_context_cache[cache_key]
    
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
            # ✅ 优化: 批量查询所有实体相关的列（单次 Neo4j 查询）
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
                
                # ✅ 优化: 扩展表过滤（使用分数过滤，跳过 LLM）
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
        tables_list = [{"id": t[0], "name": t[1], "description": t[2]} for t in sorted_tables]
        
        if not tables_list:
            all_tables_from_db = crud.schema_table.get_by_connection(db=db, connection_id=connection_id)
            tables_list = [
                {"id": table.id, "name": table.table_name, "description": table.description or ""}
                for table in all_tables_from_db
            ]
        
        table_ids = [t["id"] for t in tables_list]
        
        # ✅ 优化: 批量获取所有相关表的列（单次数据库查询）
        columns_list = []
        
        # ✅ 修复: 直接串行执行数据库查询（SQLAlchemy Session 不是线程安全的）
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
        table_name_map = {t["id"]: t["name"] for t in tables_list}
        col_name_map = {c["id"]: c["name"] for c in columns_list}
        
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
        _full_schema_context_cache[cache_key] = result
        _full_schema_context_timestamps[cache_key] = time.time()
        
        total_elapsed = time.time() - start_time
        logger.info(f"✓ Schema 获取完成 (并行优化) [{int(total_elapsed*1000)}ms] - tables: {len(tables_list)}, columns: {len(columns_list)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Schema 获取失败: {e}")
        raise Exception(f"检索表结构上下文时出错: {str(e)}")


def fetch_columns_batch_sync(db: Session, table_ids: List[int], tables_list: List[Dict]) -> List[Dict]:
    """同步批量获取列（供 run_in_executor 使用）"""
    try:
        # 尝试使用批量方法
        all_columns = crud.schema_column.get_by_table_ids(db=db, table_ids=table_ids)
    except AttributeError:
        # 降级到逐表获取
        all_columns = []
        for table_id in table_ids:
            all_columns.extend(crud.schema_column.get_by_table(db=db, table_id=table_id))
    
    table_name_map = {t["id"]: t["name"] for t in tables_list}
    
    return [
        {
            "id": col.id,
            "name": col.column_name,
            "type": col.data_type,
            "description": col.description,
            "is_primary_key": col.is_primary_key,
            "is_foreign_key": col.is_foreign_key,
            "table_id": col.table_id,
            "table_name": table_name_map.get(col.table_id, "")
        }
        for col in all_columns
    ]


def fetch_relationships_sync(db: Session, table_ids: List[int], connection_id: int, tables_list: List[Dict]) -> List:
    """同步获取关系（供 run_in_executor 使用）"""
    try:
        # 尝试使用批量方法
        all_rels = crud.schema_relationship.get_by_table_ids(db=db, table_ids=table_ids)
    except AttributeError:
        # 降级到按连接获取
        all_rels = crud.schema_relationship.get_by_connection(db=db, connection_id=connection_id)
        # 过滤只保留相关表
        all_rels = [r for r in all_rels if r.source_table_id in table_ids and r.target_table_id in table_ids]
    
    return all_rels


# ============================================================================
# 共享辅助函数 (供 dashboard_insight_graph 等模块复用)
# ============================================================================

def get_sql_syntax_guide(db_type: str) -> str:
    """
    获取数据库特定的 SQL 语法指南
    
    Args:
        db_type: 数据库类型 (MYSQL, POSTGRESQL, SQLITE, SQLSERVER, ORACLE)
        
    Returns:
        str: SQL 语法指南字符串
    """
    guides = {
        "MYSQL": "MySQL: 使用LIMIT, 反引号`, DATE_FORMAT(), 不支持FULL OUTER JOIN",
        "MARIADB": "MariaDB: 使用LIMIT, 反引号`, DATE_FORMAT(), 不支持FULL OUTER JOIN",
        "POSTGRESQL": "PostgreSQL: 使用LIMIT, 双引号\", TO_CHAR(), 支持FULL OUTER JOIN",
        "SQLITE": "SQLite: 使用LIMIT, strftime(), 不支持RIGHT JOIN/FULL OUTER JOIN",
        "SQLSERVER": "SQL Server: 使用TOP N, 方括号[], FORMAT(), 支持FULL OUTER JOIN",
        "ORACLE": "Oracle: 使用ROWNUM, 双引号\", TO_CHAR(), 需要FROM DUAL",
    }
    return guides.get(db_type.upper(), f"使用标准ANSI SQL语法 ({db_type})")


def infer_semantic_type(column_name: str, data_type: str) -> str:
    """
    推断列的语义类型
    
    Args:
        column_name: 列名
        data_type: 数据类型
        
    Returns:
        str: 语义类型 (datetime, currency, quantity, identifier, name, category, general)
    """
    name_lower = column_name.lower()
    
    if any(kw in name_lower for kw in ["date", "time", "created", "updated", "timestamp"]):
        return "datetime"
    if any(kw in name_lower for kw in ["price", "amount", "cost", "fee", "total", "money"]):
        return "currency"
    if any(kw in name_lower for kw in ["count", "quantity", "qty", "num", "number"]):
        return "quantity"
    if name_lower.endswith("_id") or name_lower == "id":
        return "identifier"
    if any(kw in name_lower for kw in ["name", "title", "label"]):
        return "name"
    if any(kw in name_lower for kw in ["status", "state", "type", "category"]):
        return "category"
    
    return "general"


def is_aggregatable_type(data_type: str) -> bool:
    """
    判断数据类型是否可聚合 (SUM, AVG, etc.)
    
    Args:
        data_type: 数据类型字符串
        
    Returns:
        bool: 是否可聚合
    """
    numeric_types = ["int", "float", "double", "decimal", "numeric", "number", "bigint", "smallint", "tinyint"]
    return any(t in data_type.lower() for t in numeric_types)


def is_groupable_type(data_type: str, column_name: str) -> bool:
    """
    判断列是否适合 GROUP BY
    
    Args:
        data_type: 数据类型字符串
        column_name: 列名
        
    Returns:
        bool: 是否适合分组
    """
    string_types = ["varchar", "char", "text", "string", "enum", "nvarchar", "nchar"]
    date_types = ["date", "datetime", "timestamp"]
    
    if any(t in data_type.lower() for t in string_types + date_types):
        return True
    if "_id" in column_name.lower() and column_name.lower() != "id":
        return True
    
    return False


def validate_sql_safety(sql: str) -> dict:
    """
    验证 SQL 安全性
    
    Args:
        sql: SQL 语句
        
    Returns:
        dict: {"valid": bool, "error": str or None, "warnings": list}
    """
    result = {"valid": True, "error": None, "warnings": []}
    sql_upper = sql.upper().strip()
    
    # 安全检查 - 危险关键字
    dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER", "CREATE"]
    for kw in dangerous_keywords:
        if kw in sql_upper and not sql_upper.startswith("SELECT"):
            result["valid"] = False
            result["error"] = f"检测到危险操作: {kw}"
            return result
    
    # 必须是 SELECT 语句
    if not sql_upper.startswith("SELECT"):
        result["valid"] = False
        result["error"] = "必须是 SELECT 语句"
        return result
    
    return result


def clean_sql_from_llm_response(sql: str) -> str:
    """
    清理 LLM 响应中的 SQL (去除 markdown 包裹)
    
    Args:
        sql: 原始 SQL 字符串
        
    Returns:
        str: 清理后的 SQL
    """
    sql = sql.strip()
    
    # 去除 markdown 代码块
    if sql.startswith("```sql"):
        sql = sql[6:]
    elif sql.startswith("```"):
        sql = sql[3:]
    
    if sql.endswith("```"):
        sql = sql[:-3]
    
    return sql.strip()
