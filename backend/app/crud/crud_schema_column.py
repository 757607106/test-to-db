from typing import List, Optional


from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.schema_column import SchemaColumn
from app.schemas.schema_column import SchemaColumnCreate, SchemaColumnUpdate


class CRUDSchemaColumn(CRUDBase[SchemaColumn, SchemaColumnCreate, SchemaColumnUpdate]):
    def get_by_table(
        self, db: Session, *, table_id: int, skip: int = 0, limit: int = 100
    ) -> List[SchemaColumn]:
        return (
            db.query(SchemaColumn)
            .filter(SchemaColumn.table_id == table_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_name_and_table(
        self, db: Session, *, column_name: str, table_id: int
    ) -> Optional[SchemaColumn]:
        return (
            db.query(SchemaColumn)
            .filter(
                SchemaColumn.column_name == column_name,
                SchemaColumn.table_id == table_id
            )
            .first()
        )

    def get_by_table_ids(
        self, db: Session, *, table_ids: List[int], limit: int = 1000
    ) -> List[SchemaColumn]:
        """
        批量获取多个表的列（性能优化）
        
        Args:
            db: 数据库会话
            table_ids: 表ID列表
            limit: 最大返回数量
            
        Returns:
            所有匹配表的列列表
        """
        if not table_ids:
            return []
        return (
            db.query(SchemaColumn)
            .filter(SchemaColumn.table_id.in_(table_ids))
            .limit(limit)
            .all()
        )

schema_column = CRUDSchemaColumn(SchemaColumn)
