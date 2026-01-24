from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.crud.base import CRUDBase
from app.models.agent_profile import AgentProfile
from app.schemas.agent_profile import AgentProfileCreate, AgentProfileUpdate

class CRUDAgentProfile(CRUDBase[AgentProfile, AgentProfileCreate, AgentProfileUpdate]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[AgentProfile]:
        return db.query(self.model).filter(self.model.name == name).first()

    def create_with_tenant(
        self, db: Session, *, obj_in: AgentProfileCreate, user_id: int, tenant_id: int
    ) -> AgentProfile:
        """Create a new agent profile for a specific tenant."""
        obj_in_data = obj_in.model_dump() if hasattr(obj_in, 'model_dump') else obj_in.dict()
        db_obj = AgentProfile(**obj_in_data, user_id=user_id, tenant_id=tenant_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_for_tenant(
        self, db: Session, *, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> List[AgentProfile]:
        """Get all profiles visible to a tenant (system profiles + tenant's own profiles)."""
        return (
            db.query(self.model)
            .filter(
                or_(
                    self.model.is_system == True,
                    self.model.tenant_id == tenant_id
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_tenant(
        self, db: Session, *, id: int, tenant_id: int
    ) -> Optional[AgentProfile]:
        """Get a profile if it's a system profile or owned by the tenant."""
        return (
            db.query(self.model)
            .filter(
                self.model.id == id,
                or_(
                    self.model.is_system == True,
                    self.model.tenant_id == tenant_id
                )
            )
            .first()
        )

    def is_owned_by_tenant(
        self, db: Session, *, id: int, tenant_id: int
    ) -> bool:
        """Check if a profile is owned by a specific tenant (not system)."""
        profile = db.query(self.model).filter(
            self.model.id == id,
            self.model.tenant_id == tenant_id,
            self.model.is_system == False
        ).first()
        return profile is not None

    def get_multi_for_user(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[AgentProfile]:
        """Get all profiles visible to a user (system profiles + user's own profiles)."""
        return (
            db.query(self.model)
            .filter(
                or_(
                    self.model.is_system == True,
                    self.model.user_id == user_id
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_user(
        self, db: Session, *, id: int, user_id: int
    ) -> Optional[AgentProfile]:
        """Get a profile if it's a system profile or owned by the user."""
        return (
            db.query(self.model)
            .filter(
                self.model.id == id,
                or_(
                    self.model.is_system == True,
                    self.model.user_id == user_id
                )
            )
            .first()
        )

    def is_owned_by_user(
        self, db: Session, *, id: int, user_id: int
    ) -> bool:
        """Check if a profile is owned by a specific user (not system)."""
        profile = db.query(self.model).filter(
            self.model.id == id,
            self.model.user_id == user_id,
            self.model.is_system == False
        ).first()
        return profile is not None

agent_profile = CRUDAgentProfile(AgentProfile)
