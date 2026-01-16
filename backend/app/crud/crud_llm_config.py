from typing import Optional, List, Union, Dict, Any
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.llm_config import LLMConfiguration
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate

class CRUDLLMConfig(CRUDBase[LLMConfiguration, LLMConfigCreate, LLMConfigUpdate]):
    def create(self, db: Session, *, obj_in: LLMConfigCreate) -> LLMConfiguration:
        """
        Create a new LLM configuration.
        允许同类型的多个模型同时启用，不再自动禁用其他配置。
        """
        return super().create(db, obj_in=obj_in)

    def update(
        self,
        db: Session,
        *,
        db_obj: LLMConfiguration,
        obj_in: Union[LLMConfigUpdate, Dict[str, Any]]
    ) -> LLMConfiguration:
        """
        Update an LLM configuration.
        允许同类型的多个模型同时启用，不再自动禁用其他配置。
        """
        return super().update(db, db_obj=db_obj, obj_in=obj_in)

    def get_active_configs(self, db: Session, model_type: Optional[str] = None) -> List[LLMConfiguration]:
        query = db.query(self.model).filter(self.model.is_active == True)
        if model_type:
            query = query.filter(self.model.model_type == model_type)
        return query.all()

llm_config = CRUDLLMConfig(LLMConfiguration)
