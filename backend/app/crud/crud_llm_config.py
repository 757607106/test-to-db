from typing import Optional, List
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.llm_config import LLMConfiguration
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate

class CRUDLLMConfig(CRUDBase[LLMConfiguration, LLMConfigCreate, LLMConfigUpdate]):
    def get_active_configs(self, db: Session, model_type: Optional[str] = None) -> List[LLMConfiguration]:
        query = db.query(self.model).filter(self.model.is_active == True)
        if model_type:
            query = query.filter(self.model.model_type == model_type)
        return query.all()

llm_config = CRUDLLMConfig(LLMConfiguration)
