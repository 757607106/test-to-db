from typing import Optional, Union
import logging
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.agent_profile import AgentProfile
from app.models.llm_config import LLMConfiguration
from app.core.llms import get_default_model
from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig

logger = logging.getLogger(__name__)

# 定义系统核心 Agent 的名称常量
CORE_AGENT_SQL_GENERATOR = "sql_generator_core"
CORE_AGENT_CHART_ANALYST = "chart_analyst_core" # 对应 Default Data Analyst
CORE_AGENT_ROUTER = "router_core"
CORE_AGENT_SUPERVISOR = "supervisor_core"  # Supervisor 协调器

# Agent 名称到显示名称的映射
AGENT_DISPLAY_NAMES = {
    CORE_AGENT_SQL_GENERATOR: "SQL 生成专家 (SQL Generator)",
    CORE_AGENT_CHART_ANALYST: "数据分析专家 (Data Analyst)", 
    CORE_AGENT_ROUTER: "意图识别路由 (Router)",
    CORE_AGENT_SUPERVISOR: "Supervisor 协调器",
}

def get_agent_llm(
    agent_name: str, 
    db: Optional[Session] = None,
    use_wrapper: bool = False
) -> Union[BaseChatModel, LLMWrapper]:
    """
    获取指定 Agent 的 LLM 模型实例。
    如果 AgentProfile 存在且配置了 LLM,则返回特定模型;
    否则返回全局默认模型。
    
    Args:
        agent_name: Agent 名称
        db: 数据库会话(可选)
        use_wrapper: 是否返回 LLMWrapper(带重试和超时保护),默认 False 保持兼容性
        
    Returns:
        BaseChatModel 或 LLMWrapper 实例
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    
    display_name = AGENT_DISPLAY_NAMES.get(agent_name, agent_name)
        
    try:
        # 1. 查找 AgentProfile
        profile = db.query(AgentProfile).filter(AgentProfile.name == agent_name).first()
        
        # 2. 如果配置了特定的 LLM
        if profile:
            if profile.llm_config_id:
                llm_config = db.query(LLMConfiguration).filter(
                    LLMConfiguration.id == profile.llm_config_id
                ).first()
                
                # 检查配置是否存在
                if not llm_config:
                    logger.warning(f"Agent [{agent_name}] LLM config not found, using default")
                    return get_default_model()
                
                # 检查配置是否启用
                if not llm_config.is_active:
                    logger.warning(f"Agent [{agent_name}] LLM config disabled, using default")
                    return get_default_model()
                
                # 使用特定配置(简化日志)
                logger.debug(f"Agent [{agent_name}] using {llm_config.provider}/{llm_config.model_name}")
                llm = get_default_model(config_override=llm_config, caller=f"agent:{agent_name}")
                        
                # 如果需要包装器,返回带重试保护的版本
                if use_wrapper:
                    wrapper_config = LLMWrapperConfig(
                        max_retries=3,
                        retry_base_delay=1.0,
                        timeout=60.0,
                    )
                    return LLMWrapper(llm=llm, config=wrapper_config, name=f"agent:{agent_name}")
                return llm
                
        # 3. 回退到全局默认
        logger.debug(f"Agent [{agent_name}] using global default")
        llm = get_default_model(caller=f"agent:{agent_name}")
                
        # 如果需要包装器,返回带重试保护的版本
        if use_wrapper:
            wrapper_config = LLMWrapperConfig(
                max_retries=3,
                retry_base_delay=1.0,
                timeout=60.0,
            )
            return LLMWrapper(llm=llm, config=wrapper_config, name=f"agent:{agent_name}")
        return llm
        
    except Exception as e:
        logger.error(f"Error fetching agent LLM for {agent_name}: {e}")
        return get_default_model()
    finally:
        if should_close:
            db.close()


def get_custom_agent_llm(profile: AgentProfile, db: Session) -> BaseChatModel:
    """
    获取自定义智能体的 LLM 模型实例。
    专门用于 Supervisor 中动态创建的自定义 agent。
    """
    if profile.llm_config_id:
        llm_config = db.query(LLMConfiguration).filter(
            LLMConfiguration.id == profile.llm_config_id
        ).first()
        
        # 检查配置是否存在
        if not llm_config:
            logger.warning(f"Custom agent [{profile.name}] LLM config not found, using default")
            return get_default_model()
        
        # 检查配置是否启用
        if not llm_config.is_active:
            logger.warning(f"Custom agent [{profile.name}] LLM config disabled, using default")
            return get_default_model()
        
        # 使用特定配置（简化日志）
        logger.debug(f"Custom agent [{profile.name}] using {llm_config.provider}/{llm_config.model_name}")
        return get_default_model(config_override=llm_config)
    
    # 回退到全局默认
    logger.debug(f"Custom agent [{profile.name}] using global default")
    return get_default_model()


def get_agent_profile(agent_name: str, db: Optional[Session] = None) -> Optional[AgentProfile]:
    """
    获取指定 Agent 的 Profile 信息。
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
        
    try:
        return db.query(AgentProfile).filter(AgentProfile.name == agent_name).first()
    except Exception as e:
        logger.error(f"Error fetching agent profile for {agent_name}: {e}", exc_info=True)
        return None
    finally:
        if should_close:
            db.close()


def ensure_system_agent_profile(
    agent_name: str,
    display_name: str,
    db: Session,
    system_prompt: Optional[str] = None
) -> AgentProfile:
    """
    确保系统内置智能体的Profile存在，不存在则创建。
    
    Args:
        agent_name: 智能体名称（如 sql_generator_core）
        display_name: 显示名称（如 SQL 生成专家）
        db: 数据库会话
        system_prompt: 可选的系统提示词
    
    Returns:
        AgentProfile实例
    """
    profile = db.query(AgentProfile).filter(AgentProfile.name == agent_name).first()
    
    if not profile:
        # 创建新的系统智能体Profile
        profile = AgentProfile(
            name=agent_name,
            role_description=display_name,
            system_prompt=system_prompt or "System Internal Agent",
            is_system=True,
            is_active=True
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        logger.info(f"Created system agent profile: {agent_name}")
    else:
        # 确保is_system标志正确
        if not profile.is_system:
            profile.is_system = True
            db.add(profile)
            db.commit()
            logger.info(f"Updated agent [{agent_name}] to system agent")
    
    return profile


def get_or_create_agent_profile(
    agent_name: str,
    defaults: dict,
    db: Session
) -> AgentProfile:
    """
    获取或创建AgentProfile。
    
    Args:
        agent_name: 智能体名称
        defaults: 创建时使用的默认值字典
        db: 数据库会话
    
    Returns:
        AgentProfile实例
    """
    profile = db.query(AgentProfile).filter(AgentProfile.name == agent_name).first()
    
    if not profile:
        # 创建新的Profile
        profile = AgentProfile(name=agent_name, **defaults)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        logger.info(f"Created agent profile: {agent_name}")
    
    return profile
