"""
查询分析器
使用 LLM 分析自然语言查询，提取关键实体和意图
"""

import re
import json
import time
import logging
from typing import Dict, Any, List, Tuple

from app.core.llms import get_default_model
from app.services.text2sql.cache import (
    query_analysis_cache,
    query_analysis_cache_timestamps,
    is_query_cache_valid,
    cleanup_query_cache,
)


logger = logging.getLogger(__name__)


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


def create_fallback_analysis(query: str) -> Dict[str, Any]:
    """创建回退分析结果"""
    return {
        "entities": extract_keywords(query),
        "relationships": [],
        "query_intent": query,
        "likely_aggregations": [],
        "time_related": False,
        "comparison_related": False
    }


def analyze_query_with_llm(query: str) -> Dict[str, Any]:
    """
    使用LLM分析自然语言查询，提取关键实体和意图
    返回包含实体、关系和查询意图的结构化分析
    
    优化：使用带TTL的缓存
    """
    # 检查缓存（带TTL验证）
    if is_query_cache_valid(query):
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
                analysis = create_fallback_analysis(query)
        else:
            analysis = create_fallback_analysis(query)

        # 缓存结果（带时间戳）
        cleanup_query_cache()  # 先清理过期缓存
        query_analysis_cache[query] = analysis
        query_analysis_cache_timestamps[query] = time.time()
        
        return analysis
    except Exception as e:
        # 如果发生任何错误，回退到关键词提取
        logger.warning(f"LLM query analysis failed: {e}, using fallback")
        analysis = create_fallback_analysis(query)
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
    from .table_matcher import basic_table_matching
    
    # 检查缓存
    cache_key = f"{query}:{hash(str(all_tables))}"
    if is_query_cache_valid(cache_key):
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
            
            analysis = result.get("analysis", create_fallback_analysis(query))
            
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
            cleanup_query_cache()
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
        analysis = create_fallback_analysis(query)
        relevant_tables = basic_table_matching(query, all_tables)
        return analysis, relevant_tables
