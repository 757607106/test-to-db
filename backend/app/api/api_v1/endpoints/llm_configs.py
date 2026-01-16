from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
import logging

from app import crud, schemas
from app.api import deps
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate
from app.models.agent_profile import AgentProfile
from app.core.llms import create_llm_from_config

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[schemas.LLMConfig])
def read_llm_configs(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve LLM configurations.
    """
    configs = crud.llm_config.get_multi(db, skip=skip, limit=limit)
    return configs

@router.post("/", response_model=schemas.LLMConfig)
def create_llm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_in: LLMConfigCreate,
) -> Any:
    """
    Create new LLM configuration.
    """
    config = crud.llm_config.create(db=db, obj_in=config_in)
    return config

@router.put("/{config_id}", response_model=schemas.LLMConfig)
def update_llm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
    config_in: LLMConfigUpdate,
) -> Any:
    """
    Update an LLM configuration.
    """
    config = crud.llm_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    config = crud.llm_config.update(db=db, db_obj=config, obj_in=config_in)
    return config

@router.delete("/{config_id}")
def delete_llm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> Any:
    """
    Delete an LLM configuration.
    Checks if any agent profiles are using this configuration before deletion.
    """
    # 1. Check if configuration exists
    config = crud.llm_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # 2. Check if any agent profiles are using this configuration
    agents_using_config = db.query(AgentProfile).filter(
        AgentProfile.llm_config_id == config_id
    ).all()
    
    if agents_using_config:
        agent_names = [agent.name for agent in agents_using_config]
        logger.warning(
            f"Attempted to delete LLM config (id={config_id}) that is in use by agents: {agent_names}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"该配置正在被以下智能体使用，请先解除绑定: {', '.join(agent_names)}"
        )
    
    # 3. Delete the configuration
    config = crud.llm_config.remove(db=db, id=config_id)
    logger.info(f"Deleted LLM config (id={config_id})")
    return {"message": "删除成功", "id": config_id}

@router.post("/test", response_model=dict)
def test_llm_connection(
    *,
    config_in: LLMConfigCreate,
) -> Any:
    """
    Test connection to LLM provider.
    Tests the configuration by sending a simple message to the LLM.
    """
    try:
        logger.info(
            f"Testing LLM connection: provider={config_in.provider}, "
            f"model={config_in.model_name}"
        )
        
        # Validate required fields
        if not config_in.provider:
            return {"success": False, "message": "提供商 (provider) 不能为空"}
        if not config_in.model_name:
            return {"success": False, "message": "模型名称 (model_name) 不能为空"}
        
        # Test based on model type
        if config_in.model_type == 'chat':
            # Use ChatOpenAI for testing (works with most providers)
            llm = ChatOpenAI(
                model=config_in.model_name,
                api_key=config_in.api_key,
                base_url=config_in.base_url,
                temperature=0,
                max_retries=1,
                timeout=10.0
            )
            response = llm.invoke("Hello, are you online?")
            logger.info(f"LLM connection test successful: {config_in.provider}/{config_in.model_name}")
            return {
                "success": True,
                "message": f"连接成功！模型响应: {response.content[:100]}..."
            }
        else:
            # TODO: Implement embedding test
            logger.info(f"Embedding test not implemented, returning mock success")
            return {
                "success": True,
                "message": "Embedding 模型测试通过 (模拟)"
            }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM connection test failed: {error_msg}", exc_info=True)
        return {
            "success": False,
            "message": f"连接失败: {error_msg}"
        }
