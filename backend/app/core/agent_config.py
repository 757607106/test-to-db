from typing import Optional
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.agent_profile import AgentProfile
from app.models.llm_config import LLMConfiguration
from app.core.llms import get_default_model

# 定义系统核心 Agent 的名称常量
CORE_AGENT_SQL_GENERATOR = "sql_generator_core"
CORE_AGENT_CHART_ANALYST = "chart_analyst_core" # 对应 Default Data Analyst
CORE_AGENT_ROUTER = "router_core"

def get_agent_llm(agent_name: str, db: Optional[Session] = None) -> BaseChatModel:
    """
    获取指定 Agent 的 LLM 模型实例。
    如果 AgentProfile 存在且配置了 LLM，则返回特定模型；
    否则返回全局默认模型。
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
        
    try:
        # 1. 查找 AgentProfile
        profile = db.query(AgentProfile).filter(AgentProfile.name == agent_name).first()
        
        # 2. 如果配置了特定的 LLM
        if profile and profile.llm_config_id:
            llm_config = db.query(LLMConfiguration).filter(LLMConfiguration.id == profile.llm_config_id).first()
            if llm_config and llm_config.is_active:
                return get_default_model(config_override=llm_config)
        
        # 3. 回退到全局默认
        return get_default_model()
        
    except Exception as e:
        print(f"Error fetching agent LLM for {agent_name}: {e}")
        return get_default_model()
    finally:
        if should_close:
            db.close()
