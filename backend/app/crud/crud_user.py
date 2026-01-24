"""CRUD operations for User model."""
from typing import Optional, Union, List
from datetime import datetime

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for User."""

    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        """Get user by email."""
        return db.query(User).filter(User.email == email).first()

    def get_by_username(self, db: Session, *, username: str) -> Optional[User]:
        """Get user by username."""
        return db.query(User).filter(User.username == username).first()

    def get_by_username_or_email(
        self, db: Session, *, username_or_email: str
    ) -> Optional[User]:
        """Get user by username or email."""
        return db.query(User).filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

    def get_multi_by_tenant(
        self, db: Session, *, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """Get all users in a tenant."""
        return (
            db.query(User)
            .filter(User.tenant_id == tenant_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        """Create new user with hashed password."""
        db_obj = User(
            username=obj_in.username,
            email=obj_in.email,
            password_hash=get_password_hash(obj_in.password),
            display_name=obj_in.display_name,
            role="user",
            is_active=True,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_with_tenant(
        self, db: Session, *, obj_in: UserCreate, tenant_id: Optional[int], role: str = "user"
    ) -> User:
        """Create new user with tenant association."""
        db_obj = User(
            username=obj_in.username,
            email=obj_in.email,
            password_hash=get_password_hash(obj_in.password),
            display_name=obj_in.display_name,
            tenant_id=tenant_id,
            role=role,
            is_active=True,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def authenticate(
        self, db: Session, *, username_or_email: str, password: str
    ) -> Optional[User]:
        """Authenticate user by username/email and password."""
        user = self.get_by_username_or_email(db, username_or_email=username_or_email)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def update_last_login(self, db: Session, *, user: User) -> User:
        """Update user's last login timestamp."""
        user.last_login_at = datetime.utcnow()
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def is_active(self, user: User) -> bool:
        """Check if user is active."""
        return user.is_active

    def is_admin(self, user: User) -> bool:
        """Check if user is super_admin."""
        return user.role == "super_admin"

    def is_tenant_admin(self, user: User) -> bool:
        """Check if user is tenant_admin or super_admin."""
        return user.role in ["super_admin", "tenant_admin"]


user = CRUDUser(User)
