"""
数据库辅助函数
提供批量获取列和关系的同步方法
"""

from typing import List, Dict
from sqlalchemy.orm import Session

from app import crud


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
    
    table_name_map = {t["id"]: t["table_name"] for t in tables_list}
    
    return [
        {
            "id": col.id,
            "column_name": col.column_name,
            "data_type": col.data_type,
            "description": col.description or "",
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
