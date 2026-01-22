"""
动态智能体工厂
根据AgentProfile创建智能体实例

支持的智能体类型:
- data_analyst: 数据分析智能体（分析数据生成洞察）
- chart_generator: 图表生成智能体（生成可视化配置）
"""
import logging
from typing import Optional, Union
from sqlalchemy.orm import Session

from app.models.agent_profile import AgentProfile
from app.core.agent_config import get_custom_agent_llm
from app.agents.agents.data_analyst_agent import DataAnalystAgent
from app.agents.agents.chart_generator_agent import ChartGeneratorAgent

logger = logging.getLogger(__name__)


def create_custom_analyst_agent(
    profile: AgentProfile,
    db: Session
) -> DataAnalystAgent:
    """
    根据AgentProfile创建自定义数据分析智能体实例
    
    自定义智能体将替换默认的 DataAnalystAgent，
    用于在 SQL 执行后进行数据分析和洞察生成。
    
    Args:
        profile: 智能体配置
        db: 数据库会话
    
    Returns:
        DataAnalystAgent实例
    """
    try:
        logger.info(f"Creating custom data analyst agent from profile: {profile.name}")
        
        # 获取自定义LLM（如果配置了）
        llm = get_custom_agent_llm(profile, db)
        
        # 获取自定义提示词
        custom_prompt = profile.system_prompt
        
        # 创建数据分析智能体实例
        agent = DataAnalystAgent(
            custom_prompt=custom_prompt,
            llm=llm
        )
        
        # 设置智能体名称（用于路由识别）
        agent.name = f"custom_analyst_{profile.id}"
        
        logger.info(
            f"Successfully created custom data analyst agent: {profile.name}, "
            f"has_custom_prompt={bool(custom_prompt)}, "
            f"has_custom_llm={profile.llm_config_id is not None}"
        )
        
        return agent
        
    except Exception as e:
        logger.error(
            f"Failed to create custom analyst agent from profile {profile.name}: {e}",
            exc_info=True
        )
        # 回退到默认智能体
        logger.warning("Falling back to default data analyst agent")
        return DataAnalystAgent()


def create_custom_agent_from_profile(
    profile: AgentProfile,
    db: Session,
    agent_type: str = "analyst"
) -> Optional[object]:
    """
    通用的智能体创建工厂函数
    
    Args:
        profile: 智能体配置
        db: 数据库会话
        agent_type: 智能体类型（analyst, sql_generator等）
    
    Returns:
        智能体实例
    """
    if agent_type == "analyst":
        return create_custom_analyst_agent(profile, db)
    else:
        logger.warning(f"Unknown agent type: {agent_type}")
        return None
