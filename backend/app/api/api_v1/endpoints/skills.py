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


# ===== Skill 自动发现 =====
# 注意：这些路由必须在 /{skill_id} 之前定义，否则会被参数路由捕获

@router.get("/discover")
async def discover_skills(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    use_llm: bool = Query(False, description="是否使用 LLM 增强分析"),
) -> Any:
    """
    自动发现 Skill 建议
    
    基于数据库表结构分析，生成 Skill 配置建议：
    - 按表名前缀分组
    - 基于外键关系优化分组
    - 可选 LLM 增强生成描述
    """
    from app.services.skill_discovery_service import skill_discovery_service
    
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        result = await skill_discovery_service.discover(
            connection_id=connection_id,
            use_llm=use_llm
        )
        
        # 转换为可序列化的格式
        suggestions = []
        for s in result.suggestions:
            suggestions.append({
                "name": s.name,
                "display_name": s.display_name,
                "description": s.description,
                "keywords": s.keywords,
                "table_names": s.table_names,
                "confidence": s.confidence,
                "reasoning": s.reasoning,
            })
        
        return {
            "suggestions": suggestions,
            "analyzed_tables": result.analyzed_tables,
            "grouped_tables": result.grouped_tables,
            "ungrouped_tables": result.ungrouped_tables,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to discover skills: {str(e)}")


@router.post("/discover/apply")
async def apply_discovered_skills(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    skill_names: List[str] = Query(..., description="要应用的 Skill 名称列表"),
) -> Any:
    """
    应用发现的 Skill 建议
    
    批量创建选中的 Skill
    """
    from app.services.skill_discovery_service import skill_discovery_service
    
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        # 先执行发现
        discovery_result = await skill_discovery_service.discover(connection_id)
        
        # 筛选要应用的建议
        suggestions_to_apply = [
            s for s in discovery_result.suggestions 
            if s.name in skill_names
        ]
        
        if not suggestions_to_apply:
            return {"success": False, "error": "No matching suggestions found"}
        
        # 应用建议
        results = await skill_discovery_service.apply_suggestions(
            connection_id=connection_id,
            suggestions=suggestions_to_apply,
            tenant_id=current_user.tenant_id
        )
        
        return {
            "success": True,
            "results": results,
            "created_count": len([r for r in results if r.get("success")])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply discovered skills: {str(e)}")


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


# ===== Skill 智能优化 =====

@router.get("/optimization/summary")
async def get_optimization_summary(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
) -> Any:
    """
    获取 Skill 优化摘要
    
    返回优化建议的概览，包括：
    - 总建议数
    - 按优先级分类
    - 按类型分类
    - 前5个建议
    """
    from app.services.skill_optimization_service import skill_optimization_service
    
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        summary = await skill_optimization_service.get_optimization_summary(connection_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get optimization summary: {str(e)}")


@router.get("/optimization/suggestions")
async def get_optimization_suggestions(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    connection_id: int = Query(..., description="数据库连接ID"),
    days: int = Query(7, description="分析最近几天的数据"),
    force_refresh: bool = Query(False, description="是否强制刷新"),
) -> Any:
    """
    获取 Skill 优化建议列表
    
    分析用户查询历史，生成配置优化建议：
    - 添加关键词
    - 创建新 Skill
    - 合并 Skills
    - 添加业务规则
    """
    from app.services.skill_optimization_service import skill_optimization_service
    
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        suggestions = await skill_optimization_service.analyze_and_suggest(
            connection_id=connection_id,
            days=days,
            force_refresh=force_refresh
        )
        
        # 转换为可序列化的格式
        result = []
        for s in suggestions:
            result.append({
                "id": s.id,
                "type": s.type.value,
                "priority": s.priority.value,
                "skill_name": s.skill_name,
                "skill_id": s.skill_id,
                "title": s.title,
                "description": s.description,
                "reasoning": s.reasoning,
                "action_data": s.action_data,
                "query_count": s.query_count,
                "failure_count": s.failure_count,
                "confidence": s.confidence,
                "example_queries": s.example_queries,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
            })
        
        return {"suggestions": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get optimization suggestions: {str(e)}")


@router.post("/optimization/apply/{suggestion_id}")
async def apply_optimization_suggestion(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    suggestion_id: str,
    connection_id: int = Query(..., description="数据库连接ID"),
) -> Any:
    """
    应用优化建议
    
    管理员审批后应用建议：
    - ADD_KEYWORD: 直接添加关键词
    - CREATE_SKILL: 返回预填数据，需要管理员在界面创建
    - 其他类型: 返回操作指引
    """
    from app.services.skill_optimization_service import skill_optimization_service
    
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="User is not associated with a tenant")
    
    # 验证连接权限
    connection = crud.db_connection.get_by_tenant(
        db=db, id=connection_id, tenant_id=current_user.tenant_id
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        result = await skill_optimization_service.apply_suggestion(
            suggestion_id=suggestion_id,
            connection_id=connection_id,
            approved_by=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply suggestion: {str(e)}")
