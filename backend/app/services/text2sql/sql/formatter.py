"""
Schema 格式化工具
将表结构上下文格式化为 LLM 提示的字符串
"""

from typing import Dict, Any


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
