"""
Schema Prompt 构建器

专门用于构建防幻觉的 Schema 提示词。

核心策略：
1. 显式列出所有可用列名
2. 明确标注主键和外键
3. 提供 JOIN 关系提示
4. 使用负面约束（禁止使用的模式）
5. 提供常见错误示例
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def build_schema_prompt(
    tables: List[Dict[str, Any]],
    columns: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]] = None,
    db_type: str = "mysql"
) -> str:
    """
    构建防幻觉的 Schema 提示词
    
    Args:
        tables: 表信息列表
        columns: 列信息列表
        relationships: 关系信息列表
        db_type: 数据库类型
        
    Returns:
        格式化的 Schema 提示词
    """
    # 构建表-列映射
    table_columns_map = {}
    table_pk_map = {}  # 主键映射
    table_fk_map = {}  # 外键映射
    all_column_names = set()  # 所有列名集合
    
    for col in columns:
        table_name = col.get('table_name', '')
        col_name = col.get('column_name', '')
        
        if table_name not in table_columns_map:
            table_columns_map[table_name] = []
            table_pk_map[table_name] = []
            table_fk_map[table_name] = []
        
        col_info = {
            'name': col_name,
            'type': col.get('data_type', ''),
            'is_pk': col.get('is_primary_key', False),
            'is_fk': col.get('is_foreign_key', False),
            'description': col.get('description', ''),
        }
        table_columns_map[table_name].append(col_info)
        all_column_names.add(f"{table_name}.{col_name}")
        
        if col_info['is_pk']:
            table_pk_map[table_name].append(col_info['name'])
        if col_info['is_fk']:
            table_fk_map[table_name].append(col_info['name'])
    
    # 构建详细的 Schema 描述
    lines = []
    lines.append("=" * 70)
    lines.append("【数据库表结构 - 请严格按照以下列名生成 SQL，禁止猜测列名】")
    lines.append("=" * 70)
    lines.append("")
    
    # 先输出所有表名列表
    table_names = [t.get('table_name', '') for t in tables]
    lines.append(f"可用的表: {', '.join(table_names)}")
    lines.append("")
    
    for table in tables:
        table_name = table.get('table_name', '')
        table_desc = table.get('description', '')
        cols = table_columns_map.get(table_name, [])
        pks = table_pk_map.get(table_name, [])
        fks = table_fk_map.get(table_name, [])
        
        lines.append("-" * 50)
        lines.append(f"表: `{table_name}`")
        if table_desc:
            lines.append(f"描述: {table_desc}")
        
        # 主键信息 - 强调主键通常是 id
        if pks:
            lines.append(f"主键: {', '.join(pks)}")
        else:
            lines.append(f"主键: id (默认，不是 {table_name}_id)")
        
        # 列信息 - 详细列出每一列
        lines.append("列名列表 (只能使用以下列名):")
        for col in cols:
            col_name = col['name']
            col_type = col['type']
            markers = []
            if col['is_pk']:
                markers.append("主键")
            if col['is_fk']:
                markers.append("外键")
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            desc_str = f" -- {col['description']}" if col.get('description') else ""
            lines.append(f"    • {col_name}: {col_type}{marker_str}{desc_str}")
        
        lines.append("")
    
    # 添加关系信息
    if relationships:
        lines.append("=" * 70)
        lines.append("【表关系 - JOIN 时请使用以下关联条件】")
        lines.append("=" * 70)
        lines.append("")
        
        for rel in relationships:
            source = f"{rel.get('source_table', '')}.{rel.get('source_column', '')}"
            target = f"{rel.get('target_table', '')}.{rel.get('target_column', '')}"
            lines.append(f"  {source} → {target}")
        lines.append("")
    
    # 添加防幻觉约束 - 更强的约束
    lines.append("=" * 70)
    lines.append("【⚠️ 严格约束 - 违反将导致 SQL 执行失败】")
    lines.append("=" * 70)
    lines.append("")
    lines.append("1. 【列名约束】只能使用上面明确列出的列名，禁止猜测或虚构")
    lines.append("2. 【主键约束】大多数表的主键是 `id`，不是 `表名_id`")
    lines.append("   例如: product 表的主键是 `id`，不是 `product_id`")
    lines.append("3. 【外键约束】外键通常命名为 `关联表名_id`")
    lines.append("   例如: sales_order_detail 表中引用 product 的外键是 `product_id`")
    lines.append("4. 【JOIN 约束】JOIN 时必须使用正确的关联字段")
    lines.append("5. 【别名约束】使用表别名时，确保引用的列在该表中存在")
    lines.append("")
    lines.append("【⚠️ 特别警告 - 常见幻觉列名】")
    lines.append("以下列名经常被错误使用，请特别注意：")
    lines.append("  ❌ total_inventory → 不存在！请使用 quantity 或 SUM(quantity)")
    lines.append("  ❌ total_sales → 不存在！请使用 SUM(amount) 或 SUM(quantity * unit_price)")
    lines.append("  ❌ avg_daily_sales → 不存在！请使用 AVG(...) 计算")
    lines.append("  ❌ product_name → 可能不存在！请检查是否是 name")
    lines.append("  ❌ category_name → 可能不存在！请检查是否是 name")
    lines.append("")
    
    # 常见错误示例 - 更具体的例子
    lines.append("【❌ 常见错误示例 - 请避免】")
    lines.append("")
    lines.append("错误1: 使用不存在的列名")
    lines.append("  ❌ SELECT i.quantity_on_hand FROM inventory i")
    lines.append("  ✓ SELECT i.quantity FROM inventory i  (正确的列名是 quantity)")
    lines.append("")
    lines.append("错误2: 错误的主键列名")
    lines.append("  ❌ SELECT p.product_id FROM product p")
    lines.append("  ✓ SELECT p.id FROM product p  (主键是 id)")
    lines.append("")
    lines.append("错误3: 错误的 JOIN 条件")
    lines.append("  ❌ JOIN sales_order so ON so.sales_order_id = ...")
    lines.append("  ✓ JOIN sales_order so ON so.id = ...  (主键是 id)")
    lines.append("")
    lines.append("错误4: 混淆主键和外键")
    lines.append("  ❌ FROM product p JOIN inventory i ON p.product_id = i.product_id")
    lines.append("  ✓ FROM product p JOIN inventory i ON p.id = i.product_id")
    lines.append("     (product 的主键是 id，inventory 的外键是 product_id)")
    lines.append("")
    
    return "\n".join(lines)


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
                        f"可用列: {', '.join(column_whitelist[table_name][:10])}"
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
