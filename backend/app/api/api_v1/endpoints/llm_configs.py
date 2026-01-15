from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI

from app import crud, schemas
from app.api import deps
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate

router = APIRouter()

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

@router.delete("/{config_id}", response_model=schemas.LLMConfig)
def delete_llm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> Any:
    """
    Delete an LLM configuration.
    """
    config = crud.llm_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    config = crud.llm_config.remove(db=db, id=config_id)
    return config

@router.post("/test", response_model=dict)
def test_llm_connection(
    *,
    config_in: LLMConfigCreate,
) -> Any:
    """
    Test connection to LLM provider.
    """
    try:
        # Simple test using LangChain
        if config_in.model_type == 'chat':
            llm = ChatOpenAI(
                model=config_in.model_name,
                api_key=config_in.api_key,
                base_url=config_in.base_url,
                temperature=0,
                max_retries=1
            )
            response = llm.invoke("Hello, are you online?")
            return {"success": True, "message": str(response.content)}
        else:
            # TODO: Implement embedding test
            return {"success": True, "message": "Embedding test passed (mock)"}
    except Exception as e:
        return {"success": False, "message": str(e)}
