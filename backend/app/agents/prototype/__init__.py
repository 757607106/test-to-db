"""
Hub-and-Spoke Supervisor 架构原型

遵循 LangGraph 官方推荐的 Supervisor 模式:
- Supervisor 作为中心枢纽
- 所有 Worker Agent 向 Supervisor 报告
- Supervisor 统一决策和汇总

原型目的:
- 验证新架构的可行性
- 与现有 Pipeline 架构并行对比
- 为正式重构提供参考实现
"""

from .hub_spoke_graph import create_hub_spoke_graph, HubSpokeGraph
from .true_supervisor import TrueSupervisor

__all__ = [
    "create_hub_spoke_graph",
    "HubSpokeGraph", 
    "TrueSupervisor"
]
