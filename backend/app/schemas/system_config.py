from typing import Optional
from pydantic import BaseModel


class SystemConfigBase(BaseModel):
    config_key: str
    config_value: Optional[str] = None
    description: Optional[str] = None


class SystemConfigCreate(SystemConfigBase):
    pass


class SystemConfigUpdate(BaseModel):
    config_value: Optional[str] = None
    description: Optional[str] = None


class SystemConfigInDBBase(SystemConfigBase):
    id: int

    class Config:
        from_attributes = True


class SystemConfig(SystemConfigInDBBase):
    pass
