"""
表匹配器
使用 LLM 和关键词匹配找到与查询相关的表
"""

import re
import json
import logging
from typing import Dict, Any, List, Tuple, Set

from app.core.llms import get_default_model
from .query_analyzer import extract_keywords


logger = logging.getLogger(__name__)


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
