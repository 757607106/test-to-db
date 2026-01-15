from typing import Optional, List, Any, Dict
from pydantic import BaseModel

class AgentProfileBase(BaseModel):
    name: str
    role_description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = []
    llm_config_id: Optional[int] = None
    is_active: bool = True

class AgentProfileCreate(AgentProfileBase):
    pass

class AgentProfileUpdate(BaseModel):
    name: Optional[str] = None
    role_description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    llm_config_id: Optional[int] = None
    is_active: Optional[bool] = None

class AgentProfileInDBBase(AgentProfileBase):
    id: int

    class Config:
        from_attributes = True

class AgentProfile(AgentProfileInDBBase):
    pass
