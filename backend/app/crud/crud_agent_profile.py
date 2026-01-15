from typing import Optional
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.agent_profile import AgentProfile
from app.schemas.agent_profile import AgentProfileCreate, AgentProfileUpdate

class CRUDAgentProfile(CRUDBase[AgentProfile, AgentProfileCreate, AgentProfileUpdate]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[AgentProfile]:
        return db.query(self.model).filter(self.model.name == name).first()

agent_profile = CRUDAgentProfile(AgentProfile)
