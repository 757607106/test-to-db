from typing import Optional
from pydantic import BaseModel, HttpUrl

class LLMConfigBase(BaseModel):
    provider: str
    base_url: Optional[str] = None
    model_name: str
    model_type: str = "chat"
    is_active: bool = True

class LLMConfigCreate(LLMConfigBase):
    api_key: Optional[str] = None

class LLMConfigUpdate(BaseModel):
    provider: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    model_type: Optional[str] = None
    is_active: Optional[bool] = None
    api_key: Optional[str] = None

class LLMConfigInDBBase(LLMConfigBase):
    id: int
    api_key: Optional[str] = None  # Should be masked in real API

    class Config:
        from_attributes = True

class LLMConfig(LLMConfigInDBBase):
    pass
