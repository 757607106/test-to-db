from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
import logging

from app import crud, models, schemas
from app.api import deps
from app.schemas.agent_profile import AgentProfileCreate, AgentProfileUpdate
from app.core.llms import get_default_model

router = APIRouter()
logger = logging.getLogger(__name__)

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
    用户创建的智能体默认 is_system=False。
    """
    # 检查名称是否已存在
    profile = crud.agent_profile.get_by_name(db, name=profile_in.name)
    if profile:
        logger.warning(f"Attempted to create agent with duplicate name: {profile_in.name}")
        raise HTTPException(status_code=400, detail="该名称的智能体配置已存在")
    
    # 确保用户创建的智能体 is_system=False
    profile_data = profile_in.dict()
    profile_data['is_system'] = False
    
    # 创建智能体
    profile = crud.agent_profile.create(db=db, obj_in=profile_data)
    logger.info(f"Created custom agent profile: {profile.name} (id={profile.id})")
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
    系统内置智能体不允许修改 name 和 role_description。
    """
    # 获取现有配置
    profile = crud.agent_profile.get(db=db, id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="智能体配置不存在")
    
    # 保护系统内置智能体
    if profile.is_system:
        # 检查是否尝试修改受保护的字段
        if profile_in.name is not None and profile_in.name != profile.name:
            logger.warning(
                f"Attempted to modify name of system agent: {profile.name} -> {profile_in.name}"
            )
            raise HTTPException(
                status_code=403,
                detail="系统内置智能体不允许修改名称"
            )
        if profile_in.role_description is not None and profile_in.role_description != profile.role_description:
            logger.warning(
                f"Attempted to modify role_description of system agent: {profile.name}"
            )
            raise HTTPException(
                status_code=403,
                detail="系统内置智能体不允许修改角色描述"
            )
        # 不允许修改 is_system 字段
        if profile_in.is_system is not None and profile_in.is_system != profile.is_system:
            logger.warning(
                f"Attempted to modify is_system flag of agent: {profile.name}"
            )
            raise HTTPException(
                status_code=403,
                detail="不允许修改智能体的系统标志"
            )
    
    # 如果修改名称，检查新名称是否已存在
    if profile_in.name is not None and profile_in.name != profile.name:
        existing = crud.agent_profile.get_by_name(db, name=profile_in.name)
        if existing:
            logger.warning(f"Attempted to rename agent to duplicate name: {profile_in.name}")
            raise HTTPException(status_code=400, detail="该名称的智能体配置已存在")
    
    # 更新配置
    profile = crud.agent_profile.update(db=db, db_obj=profile, obj_in=profile_in)
    logger.info(f"Updated agent profile: {profile.name} (id={profile.id})")
    return profile

@router.delete("/{profile_id}")
def delete_agent_profile(
    *,
    db: Session = Depends(deps.get_db),
    profile_id: int,
) -> Any:
    """
    删除智能体配置 (Delete an agent profile).
    系统内置智能体不允许删除。
    """
    # 获取配置
    profile = crud.agent_profile.get(db=db, id=profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="智能体配置不存在")
    
    # 保护系统内置智能体
    if profile.is_system:
        logger.warning(f"Attempted to delete system agent: {profile.name}")
        raise HTTPException(
            status_code=403,
            detail="系统内置智能体不允许删除"
        )
    
    # 删除配置
    profile = crud.agent_profile.remove(db=db, id=profile_id)
    logger.info(f"Deleted agent profile: {profile.name} (id={profile_id})")
    return {"message": "删除成功", "id": profile_id}

class PromptOptimizationRequest(BaseModel):
    description: str

@router.post("/optimize-prompt", response_model=str)
async def optimize_agent_prompt(
    request: PromptOptimizationRequest,
) -> Any:
    """
    智能优化 System Prompt。
    基于用户提供的角色描述，生成专业的系统提示词。
    """
    if not request.description or not request.description.strip():
        logger.warning("Attempted to optimize prompt with empty description")
        raise HTTPException(status_code=400, detail="角色描述不能为空")
    
    try:
        logger.info(f"Optimizing prompt for description: {request.description[:50]}...")
        
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
        logger.info("Prompt optimization completed successfully")
        return response.content
    
    except Exception as e:
        logger.error(f"Failed to optimize prompt: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"提示词优化失败: {str(e)}"
        )
