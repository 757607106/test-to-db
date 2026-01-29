"""
值映射处理
从数据库获取值映射并处理 SQL 中的自然语言术语替换
"""

import re
from typing import Dict, Any
from sqlalchemy.orm import Session

from app import crud


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
