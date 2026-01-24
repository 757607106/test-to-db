"""租户 CRUD 操作"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate


class CRUDTenant(CRUDBase[Tenant, TenantCreate, TenantUpdate]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[Tenant]:
        """通过名称获取租户"""
        return db.query(Tenant).filter(Tenant.name == name).first()

    def get_active_tenants(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Tenant]:
        """获取所有活跃的租户"""
        return (
            db.query(Tenant)
            .filter(Tenant.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )


tenant = CRUDTenant(Tenant)
