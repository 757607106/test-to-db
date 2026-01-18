from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.schemas.system_config import SystemConfig, SystemConfigCreate, SystemConfigUpdate

router = APIRouter()


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
