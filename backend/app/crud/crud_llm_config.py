from typing import Optional, List, Union, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.crud.base import CRUDBase
from app.models.llm_config import LLMConfiguration
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate

class CRUDLLMConfig(CRUDBase[LLMConfiguration, LLMConfigCreate, LLMConfigUpdate]):
    def create_with_tenant(
        self, db: Session, *, obj_in: LLMConfigCreate, user_id: int, tenant_id: int
    ) -> LLMConfiguration:
        """Create a new LLM configuration for a specific tenant."""
        obj_in_data = obj_in.model_dump() if hasattr(obj_in, 'model_dump') else obj_in.dict()
        db_obj = LLMConfiguration(**obj_in_data, user_id=user_id, tenant_id=tenant_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_with_user(self, db: Session, *, obj_in: LLMConfigCreate, user_id: int) -> LLMConfiguration:
        """Create a new LLM configuration for a specific user."""
        obj_in_data = obj_in.model_dump() if hasattr(obj_in, 'model_dump') else obj_in.dict()
        db_obj = LLMConfiguration(**obj_in_data, user_id=user_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create(self, db: Session, *, obj_in: LLMConfigCreate) -> LLMConfiguration:
        """Create a new LLM configuration."""
        return super().create(db, obj_in=obj_in)

    def update(
        self,
        db: Session,
        *,
        db_obj: LLMConfiguration,
        obj_in: Union[LLMConfigUpdate, Dict[str, Any]]
    ) -> LLMConfiguration:
        """Update an LLM configuration."""
        return super().update(db, db_obj=db_obj, obj_in=obj_in)

    def get_multi_by_tenant(
        self, db: Session, *, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> List[LLMConfiguration]:
        """Get all LLM configurations for a tenant."""
        return (
            db.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_tenant(self, db: Session, *, id: int, tenant_id: int) -> Optional[LLMConfiguration]:
        """Get a specific LLM configuration if it belongs to the tenant."""
        return (
            db.query(self.model)
            .filter(self.model.id == id, self.model.tenant_id == tenant_id)
            .first()
        )

    def get_multi_by_user(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[LLMConfiguration]:
        """Get all LLM configurations for a user (including system-level configs)."""
        return (
            db.query(self.model)
            .filter(or_(self.model.user_id == user_id, self.model.user_id.is_(None)))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_user(self, db: Session, *, id: int, user_id: int) -> Optional[LLMConfiguration]:
        """Get a specific LLM configuration if it belongs to the user or is system-level."""
        return (
            db.query(self.model)
            .filter(self.model.id == id)
            .filter(or_(self.model.user_id == user_id, self.model.user_id.is_(None)))
            .first()
        )

    def get_active_configs(self, db: Session, model_type: Optional[str] = None) -> List[LLMConfiguration]:
        query = db.query(self.model).filter(self.model.is_active == True)
        if model_type:
            query = query.filter(self.model.model_type == model_type)
        return query.all()

    def get_active_configs_by_tenant(
        self, db: Session, *, tenant_id: int, model_type: Optional[str] = None
    ) -> List[LLMConfiguration]:
        """Get active LLM configurations for a tenant."""
        query = (
            db.query(self.model)
            .filter(self.model.is_active == True)
            .filter(self.model.tenant_id == tenant_id)
        )
        if model_type:
            query = query.filter(self.model.model_type == model_type)
        return query.all()

    def get_active_configs_by_user(
        self, db: Session, *, user_id: int, model_type: Optional[str] = None
    ) -> List[LLMConfiguration]:
        """Get active LLM configurations for a user (including system-level configs)."""
        query = (
            db.query(self.model)
            .filter(self.model.is_active == True)
            .filter(or_(self.model.user_id == user_id, self.model.user_id.is_(None)))
        )
        if model_type:
            query = query.filter(self.model.model_type == model_type)
        return query.all()

llm_config = CRUDLLMConfig(LLMConfiguration)
