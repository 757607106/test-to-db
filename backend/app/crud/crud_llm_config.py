from typing import Optional, List, Union, Dict, Any
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.llm_config import LLMConfiguration
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate

class CRUDLLMConfig(CRUDBase[LLMConfiguration, LLMConfigCreate, LLMConfigUpdate]):
    def create(self, db: Session, *, obj_in: LLMConfigCreate) -> LLMConfiguration:
        """
        Create a new LLM configuration.
        If the new config is active, deactivate all other configs of the same type.
        """
        if obj_in.is_active:
            # Deactivate other configs of the same type
            db.query(self.model).filter(
                self.model.model_type == obj_in.model_type,
                self.model.is_active == True
            ).update({"is_active": False})
            
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
        If setting to active, deactivate all other configs of the same type.
        """
        # Check if is_active is being set to True
        is_activating = False
        model_type = db_obj.model_type

        if isinstance(obj_in, dict):
            if obj_in.get("is_active"):
                is_activating = True
                # If model_type is changed, use the new one, otherwise use existing
                if "model_type" in obj_in:
                    model_type = obj_in["model_type"]
        else:
            # Pydantic model
            if obj_in.is_active is True:
                is_activating = True
            
            # If model_type is set (not None), use it
            if getattr(obj_in, "model_type", None):
                model_type = obj_in.model_type

        if is_activating:
             db.query(self.model).filter(
                self.model.model_type == model_type,
                self.model.is_active == True,
                self.model.id != db_obj.id
            ).update({"is_active": False})
        
        return super().update(db, db_obj=db_obj, obj_in=obj_in)

    def get_active_configs(self, db: Session, model_type: Optional[str] = None) -> List[LLMConfiguration]:
        query = db.query(self.model).filter(self.model.is_active == True)
        if model_type:
            query = query.filter(self.model.model_type == model_type)
        return query.all()

llm_config = CRUDLLMConfig(LLMConfiguration)
