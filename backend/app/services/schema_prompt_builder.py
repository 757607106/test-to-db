"""
Schema Prompt 构建器

用于构建简洁的 Schema 提示词。

设计原则：
1. 简洁明了，减少干扰信息
2. 完整展示所有列名和类型
3. 明确标注主键和外键
4. 提供 JOIN 关系提示
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def build_schema_prompt(
    tables: List[Dict[str, Any]],
    columns: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]] = None,
    db_type: str = "mysql",
    user_query: str = None
) -> str:
    """
    构建简洁的 Schema 提示词（旧版本风格）
    
    简洁风格的优势：
    - 信息密度高，LLM 更容易理解
    - 所有列都完整展示，不会遗漏
    - 减少干扰信息，降低幻觉率
    
    Args:
        tables: 表信息列表
        columns: 列信息列表
        relationships: 关系信息列表
        db_type: 数据库类型
        user_query: 用户原始查询（暂不使用，保留接口兼容）
        
    Returns:
        格式化的 Schema 提示词
    """
    # 按表分组列
    columns_by_table = {}
    for col in columns:
        table_name = col.get('table_name', '')
        if table_name not in columns_by_table:
            columns_by_table[table_name] = []
        columns_by_table[table_name].append(col)
    
    # 格式化表结构（简洁的 SQL 注释风格）
    schema_str = ""
    
    for table in tables:
        table_name = table.get('table_name', '')
        table_desc = table.get('description', '')
        desc_str = f" ({table_desc})" if table_desc else ""
        
        schema_str += f"-- 表: {table_name}{desc_str}\n"
        schema_str += "-- 列:\n"
        
        if table_name in columns_by_table:
            for col in columns_by_table[table_name]:
                col_name = col.get('column_name', '')
                col_type = col.get('data_type', '')
                col_desc = col.get('description', '')
                is_pk = col.get('is_primary_key', False)
                is_fk = col.get('is_foreign_key', False)
                
                desc_str = f" ({col_desc})" if col_desc else ""
                pk_flag = " PK" if is_pk else ""
                fk_flag = " FK" if is_fk else ""
                
                schema_str += f"--   {col_name} {col_type}{pk_flag}{fk_flag}{desc_str}\n"
        
        schema_str += "\n"
    
    # 添加关系信息
    if relationships:
        schema_str += "-- 关系:\n"
        for rel in relationships:
            source_table = rel.get('source_table', '')
            source_col = rel.get('source_column', '')
            target_table = rel.get('target_table', '')
            target_col = rel.get('target_column', '')
            rel_type = rel.get('relationship_type', '')
            type_str = f" ({rel_type})" if rel_type else ""
            
            schema_str += f"-- {source_table}.{source_col} -> {target_table}.{target_col}{type_str}\n"
    
    return schema_str


def build_column_whitelist(columns: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    构建列名白名单，用于 SQL 验证
    
    Returns:
        Dict[table_name, List[column_name]]
    """
    whitelist = {}
    for col in columns:
        table_name = col.get('table_name', '')
        col_name = col.get('column_name', '')
        if table_name and col_name:
            if table_name not in whitelist:
                whitelist[table_name] = []
            whitelist[table_name].append(col_name)
    return whitelist


def validate_sql_columns(
    sql: str,
    column_whitelist: Dict[str, List[str]],
    table_aliases: Dict[str, str] = None
) -> Dict[str, Any]:
    """
    验证 SQL 中使用的列名是否在白名单中
    
    Args:
        sql: SQL 语句
        column_whitelist: 列名白名单 {table_name: [column_names]}
        table_aliases: 表别名映射 {alias: table_name}
        
    Returns:
        验证结果
    """
    import re
    
    errors = []
    warnings = []
    
    # 如果没有提供别名映射，尝试从 SQL 中提取
    if table_aliases is None:
        table_aliases = _extract_table_aliases(sql)
    
    # 提取 SQL 中的列引用 (alias.column 或 table.column)
    # 匹配模式: word.word 或 word.`word`
    column_refs = re.findall(r'(\w+)\.`?(\w+)`?', sql)
    
    # SQL 函数列表（这些不是表别名）
    sql_functions = {
        'DATE_FORMAT', 'SUM', 'COUNT', 'AVG', 'MAX', 'MIN', 'CURDATE', 
        'DATE_SUB', 'DATE_ADD', 'NOW', 'YEAR', 'MONTH', 'DAY', 'HOUR',
        'MINUTE', 'SECOND', 'CONCAT', 'SUBSTRING', 'TRIM', 'UPPER', 
        'LOWER', 'COALESCE', 'IFNULL', 'NULLIF', 'CAST', 'CONVERT',
        'ROUND', 'FLOOR', 'CEIL', 'ABS', 'MOD', 'POWER', 'SQRT'
    }
    
    for alias_or_table, column in column_refs:
        # 跳过函数调用
        if alias_or_table.upper() in sql_functions:
            continue
        
        # 解析表名
        table_name = alias_or_table
        if alias_or_table in table_aliases:
            table_name = table_aliases[alias_or_table]
        
        # 检查列是否存在
        if table_name in column_whitelist:
            if column not in column_whitelist[table_name]:
                # 尝试找到相似的列名
                similar = _find_similar_column(column, column_whitelist[table_name])
                if similar:
                    errors.append(
                        f"列 `{alias_or_table}.{column}` 不存在于表 `{table_name}` 中，"
                        f"您是否想使用 `{similar}`？"
                    )
                else:
                    errors.append(
                        f"列 `{alias_or_table}.{column}` 不存在于表 `{table_name}` 中。"
                        f"可用列: {', '.join(column_whitelist[table_name])}"
                    )
        else:
            # 表名可能是别名，尝试在所有表中查找
            found = False
            found_in_table = None
            for t, cols in column_whitelist.items():
                if column in cols:
                    found = True
                    found_in_table = t
                    break
            
            if not found:
                # 列在任何表中都不存在
                all_columns = set()
                for cols in column_whitelist.values():
                    all_columns.update(cols)
                
                similar = _find_similar_column(column, list(all_columns))
                if similar:
                    errors.append(
                        f"列 `{column}` 在任何表中都不存在，您是否想使用 `{similar}`？"
                    )
                else:
                    warnings.append(f"无法验证列 `{alias_or_table}.{column}`")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "table_aliases": table_aliases
    }


def _extract_table_aliases(sql: str) -> Dict[str, str]:
    """
    从 SQL 中提取表别名映射
    
    Args:
        sql: SQL 语句
        
    Returns:
        Dict[alias, table_name]
    """
    import re
    
    aliases = {}
    sql_upper = sql.upper()
    
    # 匹配 FROM table AS alias 或 FROM table alias
    # 以及 JOIN table AS alias 或 JOIN table alias
    patterns = [
        r'\bFROM\s+`?(\w+)`?\s+(?:AS\s+)?`?(\w+)`?(?:\s|,|JOIN|WHERE|GROUP|ORDER|LIMIT|$)',
        r'\bJOIN\s+`?(\w+)`?\s+(?:AS\s+)?`?(\w+)`?\s+ON',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            table_name = match.group(1)
            alias = match.group(2)
            # 确保别名不是 SQL 关键字
            if alias.upper() not in ['ON', 'WHERE', 'GROUP', 'ORDER', 'LIMIT', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER']:
                aliases[alias] = table_name
    
    return aliases


def _find_similar_column(column: str, available_columns: List[str]) -> Optional[str]:
    """
    找到与给定列名最相似的可用列名
    
    Args:
        column: 要查找的列名
        available_columns: 可用的列名列表
        
    Returns:
        最相似的列名，如果没有找到则返回 None
    """
    if not available_columns:
        return None
    
    column_lower = column.lower()
    best_match = None
    best_score = 0
    
    for avail in available_columns:
        avail_lower = avail.lower()
        
        # 完全包含
        if column_lower in avail_lower or avail_lower in column_lower:
            score = 0.8
        # 前缀匹配
        elif column_lower.startswith(avail_lower[:3]) or avail_lower.startswith(column_lower[:3]):
            score = 0.5
        # 共同字符比例
        else:
            common = set(column_lower) & set(avail_lower)
            score = len(common) / max(len(column_lower), len(avail_lower))
        
        if score > best_score:
            best_score = score
            best_match = avail
    
    return best_match if best_score > 0.4 else None


__all__ = [
    "build_schema_prompt",
    "build_column_whitelist",
    "validate_sql_columns",
    "_extract_table_aliases",
    "_find_similar_column",
]
