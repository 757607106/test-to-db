from typing import Any, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app import crud
from app.api import deps
from app.schemas.system_config import SystemConfig, SystemConfigCreate, SystemConfigUpdate

router = APIRouter()


# ============================================================================
# SQL 增强配置相关的数据模型
# ============================================================================

class SQLEnhancementConfig(BaseModel):
    """SQL 增强功能配置"""
    # QA 样本检索配置
    qa_sample_enabled: bool = False  # 关闭：避免样本干扰 LLM 判断
    qa_sample_min_similarity: float = 0.85
    qa_sample_top_k: int = 3
    qa_sample_verified_only: bool = True
    
    # 指标库配置
    metrics_enabled: bool = False  # 关闭：避免指标定义干扰 LLM 判断
    metrics_max_count: int = 3
    
    # 枚举值提示配置
    enum_hints_enabled: bool = False  # 关闭：避免枚举值干扰 LLM 判断
    enum_max_values: int = 20
    
    # 简化流程配置
    simplified_flow_enabled: bool = True
    skip_clarification_for_clear_queries: bool = True
    
    # 缓存配置
    cache_mode: str = "simple"  # simple | full


# SQL 增强配置的 key 前缀
SQL_ENHANCEMENT_PREFIX = "sql_enhancement_"

# 默认配置
DEFAULT_SQL_ENHANCEMENT_CONFIG = SQLEnhancementConfig()


@router.get("/{config_key}", response_model=SystemConfig)
def get_system_config(
    *,
    db: Session = Depends(deps.get_db),
    config_key: str,
) -> Any:
    """
    Get system configuration by key
    """
    config = crud.system_config.get_by_key(db, config_key=config_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration key '{config_key}' not found")
    return config


@router.put("/{config_key}", response_model=SystemConfig)
def update_system_config(
    *,
    db: Session = Depends(deps.get_db),
    config_key: str,
    config_in: SystemConfigUpdate,
) -> Any:
    """
    Update system configuration
    """
    config = crud.system_config.get_by_key(db, config_key=config_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration key '{config_key}' not found")
    
    config = crud.system_config.update(db, db_obj=config, obj_in=config_in)
    return config


@router.post("/default-embedding/{llm_config_id}")
def set_default_embedding_model(
    *,
    db: Session = Depends(deps.get_db),
    llm_config_id: int,
) -> Any:
    """
    Set the default embedding model
    """
    # Verify the LLM config exists and is an embedding model
    llm_config = crud.llm_config.get(db, id=llm_config_id)
    if not llm_config:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    
    if llm_config.model_type != "embedding":
        raise HTTPException(
            status_code=400, 
            detail=f"LLM configuration must be of type 'embedding', got '{llm_config.model_type}'"
        )
    
    if not llm_config.is_active:
        raise HTTPException(status_code=400, detail="LLM configuration must be active")
    
    # Set as default
    config = crud.system_config.set_default_embedding_model_id(db, llm_config_id=llm_config_id)
    
    # Clear VectorService cache to force reload
    from app.services.hybrid_retrieval_service import VectorServiceFactory
    VectorServiceFactory.clear_instances()
    
    return {
        "message": "Default embedding model updated successfully",
        "config_key": config.config_key,
        "llm_config_id": llm_config_id,
        "provider": llm_config.provider,
        "model_name": llm_config.model_name
    }


@router.delete("/default-embedding")
def clear_default_embedding_model(
    *,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Clear the default embedding model (fall back to environment variables)
    """
    config = crud.system_config.set_default_embedding_model_id(db, llm_config_id=None)
    
    # Clear VectorService cache to force reload
    from app.services.hybrid_retrieval_service import VectorServiceFactory
    VectorServiceFactory.clear_instances()
    
    return {
        "message": "Default embedding model cleared, will use environment variables",
        "config_key": config.config_key
    }


@router.get("/default-embedding/current", response_model=dict)
def get_default_embedding_model(
    *,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Get the current default embedding model configuration
    """
    config_id = crud.system_config.get_default_embedding_model_id(db)
    
    if not config_id:
        return {
            "source": "environment_variables",
            "llm_config_id": None,
            "message": "Using embedding model from environment variables"
        }
    
    llm_config = crud.llm_config.get(db, id=config_id)
    if not llm_config:
        return {
            "source": "environment_variables",
            "llm_config_id": None,
            "message": "Configured embedding model not found, falling back to environment variables"
        }
    
    return {
        "source": "database",
        "llm_config_id": llm_config.id,
        "provider": llm_config.provider,
        "model_name": llm_config.model_name,
        "base_url": llm_config.base_url,
        "is_active": llm_config.is_active
    }


# ============================================================================
# SQL 增强配置 API
# ============================================================================

@router.get("/sql-enhancement/config", response_model=SQLEnhancementConfig)
def get_sql_enhancement_config(
    *,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    获取 SQL 增强功能配置
    
    包括：
    - QA 样本检索配置
    - 指标库配置
    - 枚举值提示配置
    - 简化流程配置
    - 缓存配置
    """
    import json
    
    config_key = f"{SQL_ENHANCEMENT_PREFIX}config"
    config = crud.system_config.get_by_key(db, config_key=config_key)
    
    if not config or not config.config_value:
        return DEFAULT_SQL_ENHANCEMENT_CONFIG
    
    try:
        config_dict = json.loads(config.config_value)
        return SQLEnhancementConfig(**config_dict)
    except (json.JSONDecodeError, ValueError):
        return DEFAULT_SQL_ENHANCEMENT_CONFIG


@router.put("/sql-enhancement/config", response_model=SQLEnhancementConfig)
def update_sql_enhancement_config(
    *,
    db: Session = Depends(deps.get_db),
    config_in: SQLEnhancementConfig,
) -> Any:
    """
    更新 SQL 增强功能配置
    """
    import json
    
    config_key = f"{SQL_ENHANCEMENT_PREFIX}config"
    config_value = json.dumps(config_in.model_dump())
    
    crud.system_config.set_value(
        db,
        config_key=config_key,
        config_value=config_value,
        description="SQL 增强功能配置（QA样本、指标库、枚举提示等）"
    )
    
    return config_in


@router.post("/sql-enhancement/reset")
def reset_sql_enhancement_config(
    *,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    重置 SQL 增强功能配置为默认值
    """
    import json
    
    config_key = f"{SQL_ENHANCEMENT_PREFIX}config"
    config_value = json.dumps(DEFAULT_SQL_ENHANCEMENT_CONFIG.model_dump())
    
    crud.system_config.set_value(
        db,
        config_key=config_key,
        config_value=config_value,
        description="SQL 增强功能配置（QA样本、指标库、枚举提示等）"
    )
    
    return {
        "message": "SQL 增强配置已重置为默认值",
        "config": DEFAULT_SQL_ENHANCEMENT_CONFIG.model_dump()
    }


# ============================================================================
# 辅助函数：获取 SQL 增强配置（供其他模块使用）
# ============================================================================

def get_sql_enhancement_settings() -> SQLEnhancementConfig:
    """
    获取 SQL 增强配置（供其他模块调用）
    
    优先从数据库读取，如果没有则返回默认配置
    """
    import json
    from app.db.session import get_db_session
    
    try:
        with get_db_session() as db:
            config_key = f"{SQL_ENHANCEMENT_PREFIX}config"
            config = crud.system_config.get_by_key(db, config_key=config_key)
            
            if config and config.config_value:
                config_dict = json.loads(config.config_value)
                return SQLEnhancementConfig(**config_dict)
    except Exception:
        pass
    
    return DEFAULT_SQL_ENHANCEMENT_CONFIG
