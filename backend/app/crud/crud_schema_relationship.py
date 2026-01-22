from typing import List, Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.schema_relationship import SchemaRelationship
from app.schemas.schema_relationship import SchemaRelationshipCreate, SchemaRelationshipUpdate


class CRUDSchemaRelationship(CRUDBase[SchemaRelationship, SchemaRelationshipCreate, SchemaRelationshipUpdate]):
    def get_by_connection(
        self, db: Session, *, connection_id: int, skip: int = 0, limit: int = 100
    ) -> List[SchemaRelationship]:
        return (
            db.query(SchemaRelationship)
            .filter(SchemaRelationship.connection_id == connection_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_source_table(
        self, db: Session, *, source_table_id: int
    ) -> List[SchemaRelationship]:
        return (
            db.query(SchemaRelationship)
            .filter(SchemaRelationship.source_table_id == source_table_id)
            .all()
        )

    def get_by_target_table(
        self, db: Session, *, target_table_id: int
    ) -> List[SchemaRelationship]:
        return (
            db.query(SchemaRelationship)
            .filter(SchemaRelationship.target_table_id == target_table_id)
            .all()
        )

    def get_by_columns(
        self, db: Session, *, source_column_id: int, target_column_id: int
    ) -> Optional[SchemaRelationship]:
        return (
            db.query(SchemaRelationship)
            .filter(
                SchemaRelationship.source_column_id == source_column_id,
                SchemaRelationship.target_column_id == target_column_id
            )
            .first()
        )

    def get_by_table_ids(
        self, db: Session, *, table_ids: List[int], limit: int = 500
    ) -> List[SchemaRelationship]:
        """
        批量获取涉及指定表的关系（性能优化）
        
        Args:
            db: 数据库会话
            table_ids: 表ID列表
            limit: 最大返回数量
            
        Returns:
            涉及指定表的所有关系
        """
        if not table_ids:
            return []
        from sqlalchemy import or_
        return (
            db.query(SchemaRelationship)
            .filter(
                or_(
                    SchemaRelationship.source_table_id.in_(table_ids),
                    SchemaRelationship.target_table_id.in_(table_ids)
                )
            )
            .limit(limit)
            .all()
        )

schema_relationship = CRUDSchemaRelationship(SchemaRelationship)
