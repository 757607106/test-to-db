"""
图表生成代理
负责根据SQL查询结果生成合适的数据可视化图表
"""
import asyncio
from typing import Dict, Any, List
from langchain_core.tools import tool
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.core.message_utils import MCPToolWrapper
from app.schemas.agent_message import ToolResponse


# 初始化MCP图表服务器客户端
def _initialize_chart_client():
    """初始化图表生成客户端并包装工具"""
    try:
        client = MultiServerMCPClient(
            {
                "mcp-server-chart": {
                    "command": "npx",
                    "args": ["-y", "@antv/mcp-server-chart"],
                    "transport": "stdio",
                }
            }
        )
        chart_tools = asyncio.run(client.get_tools())
        
        # 使用MCPToolWrapper包装每个MCP工具
        wrapped_tools = []
        for tool in chart_tools:
            tool_name = getattr(tool, "name", "unknown_tool")
            wrapped_tool = MCPToolWrapper(tool, tool_name)
            wrapped_tools.append(wrapped_tool)
        
        return client, wrapped_tools
    except Exception as e:
        print(f"图表客户端初始化失败: {e}")
        return None, []


# 全局图表客户端和包装后的工具
CHART_CLIENT, CHART_TOOLS = _initialize_chart_client()


# ============================================================================
# 已移除本地图表工具（2026-01-21）
# 移除的工具：analyze_data_for_chart, generate_chart_config, should_generate_chart
# 移除的辅助函数：_recommend_chart_type
# 原因：已被 MCP 图表工具（@antv/mcp-server-chart）替代
# ============================================================================


class ChartGeneratorAgent:
    """图表生成代理"""
    
    def __init__(self, custom_prompt: str = None, llm = None):
        """
        初始化图表生成智能体
        
        Args:
            custom_prompt: 自定义系统提示词（可选）
            llm: 自定义LLM模型（可选）
        """
        self.name = "chart_generator_agent"
        self.custom_prompt = custom_prompt
        self.llm = llm or get_default_model()
        
        # 使用 MCP 图表工具
        self.tools = []
        
        # 如果包装后的MCP图表工具可用，添加到工具列表
        if CHART_TOOLS:
            self.tools.extend(CHART_TOOLS)
            print(f"图表生成代理已加载 {len(CHART_TOOLS)} 个MCP工具（已包装）")
        
        # 创建ReAct代理，使用包装后的工具
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """
        创建系统提示
        如果提供了custom_prompt，使用它；否则使用默认提示词
        """
        if self.custom_prompt:
            return self.custom_prompt
        
        return """你是一个专业的数据可视化专家。

**核心职责**: 根据 SQL 查询结果生成数据可视化图表

**前置条件**: Supervisor 已经判断需要生成图表才会调用你

**工作流程**:
1. 分析查询结果数据的结构特征
2. 选择最合适的图表类型
3. 使用 MCP 图表工具生成图表
4. **只返回图表配置，不重复查询结果**

**图表类型选择**:
- 趋势数据 → 折线图
- 分布对比 → 柱状图
- 占比分析 → 饼图
- 多维对比 → 雷达图

**禁止的行为**:
- ❌ 不要重新输出查询结果数据
- ❌ 不要生成"根据查询结果..."的总结
- ❌ 不要判断是否需要图表（这由 Supervisor 决定）
- ❌ 不要重复描述已有数据

**输出格式**: 只返回图表配置，不添加数据总结"""

    async def generate_chart(self, state: SQLMessageState) -> Dict[str, Any]:
        """生成图表"""
        try:
            # 调用代理处理
            result = await self.agent.ainvoke(state)
            
            return {
                "messages": result.get("messages", []),
                "current_stage": "completed"
            }
            
        except Exception as e:
            # 记录错误
            error_info = {
                "stage": "chart_generation",
                "error": str(e),
                "retry_count": state.get("retry_count", 0)
            }
            
            state["error_history"].append(error_info)
            state["current_stage"] = "error_recovery"
            
            return {
                "messages": [AIMessage(content=f"图表生成失败: {str(e)}")],
                "current_stage": "error_recovery"
            }


# 创建全局实例
chart_generator_agent = ChartGeneratorAgent()
