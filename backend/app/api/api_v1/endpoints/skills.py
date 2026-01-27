"""
Skills API 端点 (Skills Endpoints)

提供 Skills-SQL-Assistant 架构的 REST API：
- Skills CRUD 操作
- Skill 内容加载（Progressive Disclosure）
- 零配置状态检查
- 自动发现功能（Phase 2 实现）
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app import crud
from app.schemas.skill import (
    SkillCreate, SkillUpdate, Skill, SkillLoadResult,
    SkillListResponse, SkillStatusResponse
)
from app.services.skill_service import skill_service

router = APIRouter()


# ===== Skills CRUD =====

@router.post("", response_model=Skill)
async def create_skill(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    skill_data: SkillCreate,
) -> Any:
    """
    创建 Skill（业务领域）
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=skill_data.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # 检查名称唯一性
    existing = await skill_service.get_skill_by_name(
        skill_data.name, skill_data.connection_id
    )
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Skill with name '{skill_data.name}' already exists for this connection"
        )
    
    try:
        skill = await skill_service.create_skill(skill_data, current_user.tenant_id)
        return skill
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create skill: {str(e)}")


@router.get("", response_model=SkillListResponse)
async def list_skills(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    include_inactive: bool = Query(False, description="是否包含未激活的 Skill"),
) -> Any:
    """
    获取 Skill 列表
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        skills = await skill_service.get_skills_by_connection(
            connection_id=connection_id,
            include_inactive=include_inactive
        )
        return SkillListResponse(
            skills=skills,
            total=len(skills),
            has_skills_configured=len(skills) > 0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list skills: {str(e)}")


@router.get("/status", response_model=SkillStatusResponse)
async def get_skills_status(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
) -> Any:
    """
    获取 Skills 配置状态（用于判断是否启用 Skill 模式）
    
    零配置兼容的核心端点
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        has_skills = await skill_service.has_skills_configured(connection_id)
        skills = await skill_service.get_skills_by_connection(connection_id) if has_skills else []
        
        return SkillStatusResponse(
            has_skills_configured=has_skills,
            skills_count=len(skills),
            mode="skill" if has_skills else "default"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get skills status: {str(e)}")


@router.get("/{skill_id}", response_model=Skill)
async def get_skill(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    skill_id: int,
) -> Any:
    """
    获取单个 Skill 详情
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    try:
        skill = await skill_service.get_skill(skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        
        # 验证连接权限
        connection = crud.db_connection.get_by_tenant(
            db=db, id=skill.connection_id, tenant_id=current_user.tenant_id
        )
        if not connection:
            raise HTTPException(status_code=404, detail="Skill not found")
        
        return skill
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get skill: {str(e)}")


@router.put("/{skill_id}", response_model=Skill)
async def update_skill(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    skill_id: int,
    skill_data: SkillUpdate,
) -> Any:
    """
    更新 Skill
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 获取现有 Skill
    existing_skill = await skill_service.get_skill(skill_id)
    if not existing_skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=existing_skill.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    # 如果更新名称，检查唯一性
    if skill_data.name and skill_data.name != existing_skill.name:
        name_exists = await skill_service.get_skill_by_name(
            skill_data.name, existing_skill.connection_id
        )
        if name_exists:
            raise HTTPException(
                status_code=400,
                detail=f"Skill with name '{skill_data.name}' already exists for this connection"
            )
    
    try:
        skill = await skill_service.update_skill(skill_id, skill_data)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return skill
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update skill: {str(e)}")


@router.delete("/{skill_id}")
async def delete_skill(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    skill_id: int,
) -> Any:
    """
    删除 Skill
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 获取现有 Skill
    existing_skill = await skill_service.get_skill(skill_id)
    if not existing_skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=existing_skill.connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    try:
        success = await skill_service.delete_skill(skill_id)
        if not success:
            raise HTTPException(status_code=404, detail="Skill not found")
        return {"success": True, "message": f"Skill {skill_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete skill: {str(e)}")


# ===== Skill 内容加载 =====

@router.get("/{skill_name}/content", response_model=SkillLoadResult)
async def load_skill_content(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    skill_name: str,
    connection_id: int = Query(..., description="数据库连接ID"),
) -> Any:
    """
    加载 Skill 完整内容（Progressive Disclosure 核心端点）
    
    返回内容：
    - Schema（表、列、关系）- 仅限于 Skill 关联的表
    - 关联的指标定义
    - 关联的 JOIN 规则
    - 业务规则
    - 常用查询模式
    - 枚举字段值
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        result = await skill_service.load_skill(skill_name, connection_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load skill content: {str(e)}")


# ===== Skill Prompt 生成 =====

@router.get("/prompt-section", response_model=dict)
async def get_skill_prompt_section(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
) -> Any:
    """
    获取 Skill 提示词段落（注入到 System Prompt）
    
    如果没有配置 Skill，返回 null（使用现有模式）
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        prompt_section = await skill_service.get_skill_prompt_section(connection_id)
        return {
            "has_skills": prompt_section is not None,
            "prompt_section": prompt_section
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get skill prompt section: {str(e)}")


# ===== 占位：Phase 2 自动发现功能 =====

# @router.get("/discover", response_model=SkillDiscoverResponse)
# async def discover_skills(...):
#     """自动发现 Skill 建议（Phase 2 实现）"""
#     pass

# @router.post("/apply-suggestions")
# async def apply_skill_suggestions(...):
#     """应用 Skill 建议（Phase 2 实现）"""
#     pass
