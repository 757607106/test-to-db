"""
类型推断工具
提供列语义类型推断和聚合/分组判断
"""


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
