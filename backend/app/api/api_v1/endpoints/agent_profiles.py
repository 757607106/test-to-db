from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage

from app import crud, models, schemas
from app.api import deps
from app.schemas.agent_profile import AgentProfileCreate, AgentProfileUpdate
from app.core.llms import get_default_model

router = APIRouter()

@router.get("/", response_model=List[schemas.AgentProfile])
def read_agent_profiles(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    is_system: Optional[bool] = None,
) -> Any:
    """
    获取智能体配置列表 (Retrieve agent profiles).
    """
    if is_system is not None:
        profiles = db.query(models.AgentProfile).filter(models.AgentProfile.is_system == is_system).offset(skip).limit(limit).all()
    else:
        profiles = crud.agent_profile.get_multi(db, skip=skip, limit=limit)
    return profiles

@router.post("/", response_model=schemas.AgentProfile)
def create_agent_profile(
    *,
    db: Session = Depends(deps.get_db),
    profile_in: AgentProfileCreate,
) -> Any:
    """
    创建新的智能体配置 (Create new agent profile).
    """
    profile = crud.agent_profile.get_by_name(db, name=profile_in.name)
    if profile:
        raise HTTPException(status_code=400, detail="该名称的智能体配置已存在")
    profile = crud.agent_profile.create(db=db, obj_in=profile_in)
    return profile

@router.put("/{profile_id}", response_model=schemas.AgentProfile)
def update_agent_profile(
    *,
    db: Session = Depends(deps.get_db),
    profile_id: int,
    profile_in: AgentProfileUpdate,
) -> Any:
    """
    更新智能体配置 (Update an agent profile).
    """
    profile = crud.agent_profile.get(db=db, id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="智能体配置不存在")
    profile = crud.agent_profile.update(db=db, db_obj=profile, obj_in=profile_in)
    return profile

@router.delete("/{profile_id}", response_model=schemas.AgentProfile)
def delete_agent_profile(
    *,
    db: Session = Depends(deps.get_db),
    profile_id: int,
) -> Any:
    """
    删除智能体配置 (Delete an agent profile).
    """
    profile = crud.agent_profile.get(db=db, id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="智能体配置不存在")
    profile = crud.agent_profile.remove(db=db, id=profile_id)
    return profile

class PromptOptimizationRequest(BaseModel):
    description: str

@router.post("/optimize-prompt", response_model=str)
async def optimize_agent_prompt(
    request: PromptOptimizationRequest,
) -> Any:
    """
    智能优化 System Prompt
    """
    llm = get_default_model()
    
    meta_prompt = """你是一个专业的 AI 提示词工程师 (Prompt Engineer)。
你的任务是将用户简单的角色描述，转化为结构化、专业、高质量的 System Prompt。

生成的 System Prompt 应包含以下部分：
1. **角色定义**: 明确智能体的身份和职责。
2. **核心目标**: 智能体需要达成的主要目标。
3. **能力与限制**: 智能体能做什么，不能做什么。
4. **输出风格**: 回复的语气、格式要求。
5. **工作流程**: (可选) 如果有特定的步骤。

请直接输出优化后的 System Prompt 内容，不要包含任何解释性文字。"""

    messages = [
        SystemMessage(content=meta_prompt),
        HumanMessage(content=f"用户描述: {request.description}")
    ]
    
    response = await llm.ainvoke(messages)
    return response.content
