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


@tool
def analyze_data_for_chart(data: Dict[str, Any], query_context: str) -> ToolResponse:
    """
    分析数据特征，确定最适合的图表类型
    
    Args:
        data: SQL查询结果数据
        query_context: 查询上下文信息
        
    Returns:
        ToolResponse: 图表类型建议和配置信息
    """
    try:
        if not data or not isinstance(data, dict):
            return ToolResponse(
                status="error",
                error="无效的数据格式"
            )
        
        # 分析数据结构
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        
        if not columns or not rows:
            return ToolResponse(
                status="error",
                error="数据为空或格式不正确"
            )
        
        # 数据特征分析
        num_columns = len(columns)
        num_rows = len(rows)
        
        # 分析列类型
        numeric_columns = []
        text_columns = []
        date_columns = []
        
        if rows:
            first_row = rows[0]
            for i, col in enumerate(columns):
                if i < len(first_row):
                    value = first_row[i]
                    if isinstance(value, (int, float)):
                        numeric_columns.append(col)
                    elif isinstance(value, str):
                        # 简单的日期检测
                        if any(keyword in col.lower() for keyword in ['date', 'time', 'year', 'month']):
                            date_columns.append(col)
                        else:
                            text_columns.append(col)
        
        # 图表类型推荐逻辑
        chart_recommendation = _recommend_chart_type(
            num_columns, num_rows, numeric_columns, text_columns, date_columns, query_context
        )
        
        return ToolResponse(
            status="success",
            data={
                "data_analysis": {
                    "total_columns": num_columns,
                    "total_rows": num_rows,
                    "numeric_columns": numeric_columns,
                    "text_columns": text_columns,
                    "date_columns": date_columns
                },
                "chart_recommendation": chart_recommendation
            }
        )
        
    except Exception as e:
        return ToolResponse(
            status="error",
            error=str(e)
        )


def _recommend_chart_type(num_columns: int, num_rows: int, numeric_cols: List[str], 
                         text_cols: List[str], date_cols: List[str], context: str) -> Dict[str, Any]:
    """推荐图表类型的内部逻辑"""
    
    # 基于查询上下文的关键词分析
    context_lower = context.lower()
    
    # 趋势分析查询
    if any(keyword in context_lower for keyword in ['趋势', 'trend', '时间', 'time', '变化', 'change']):
        if date_cols and numeric_cols:
            return {
                "type": "line",
                "reason": "检测到时间序列数据，适合用折线图显示趋势",
                "x_axis": date_cols[0],
                "y_axis": numeric_cols[0] if numeric_cols else None
            }
    
    # 比较分析查询
    if any(keyword in context_lower for keyword in ['比较', 'compare', '对比', '排名', 'rank', '最高', '最低']):
        if text_cols and numeric_cols:
            return {
                "type": "bar",
                "reason": "检测到比较分析需求，适合用柱状图显示",
                "x_axis": text_cols[0],
                "y_axis": numeric_cols[0] if numeric_cols else None
            }
    
    # 占比分析查询
    if any(keyword in context_lower for keyword in ['占比', 'percentage', '比例', 'proportion', '分布', 'distribution']):
        if text_cols and numeric_cols:
            return {
                "type": "pie",
                "reason": "检测到占比分析需求，适合用饼图显示",
                "category": text_cols[0],
                "value": numeric_cols[0] if numeric_cols else None
            }
    
    # 默认推荐逻辑
    if num_columns == 2 and len(numeric_cols) == 1 and len(text_cols) == 1:
        if num_rows <= 10:
            return {
                "type": "pie",
                "reason": "数据量较小，适合用饼图显示分布",
                "category": text_cols[0],
                "value": numeric_cols[0]
            }
        else:
            return {
                "type": "bar",
                "reason": "数据量适中，适合用柱状图显示",
                "x_axis": text_cols[0],
                "y_axis": numeric_cols[0]
            }
    
    elif len(numeric_cols) >= 2:
        return {
            "type": "scatter",
            "reason": "多个数值列，适合用散点图显示相关性",
            "x_axis": numeric_cols[0],
            "y_axis": numeric_cols[1]
        }
    
    else:
        return {
            "type": "table",
            "reason": "数据结构复杂，建议使用表格显示",
            "columns": text_cols + numeric_cols
        }


@tool
def generate_chart_config(chart_type: str, data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成图表配置
    
    Args:
        chart_type: 图表类型
        data: 数据
        config: 配置参数
        
    Returns:
        图表配置信息
    """
    try:
        chart_config = {
            "type": chart_type,
            "data": data,
            "title": config.get("title", "数据可视化图表"),
            "width": config.get("width", 800),
            "height": config.get("height", 600)
        }
        
        # 根据图表类型添加特定配置
        if chart_type == "bar":
            chart_config.update({
                "xField": config.get("x_axis"),
                "yField": config.get("y_axis"),
                "color": "#1890ff"
            })
        elif chart_type == "line":
            chart_config.update({
                "xField": config.get("x_axis"),
                "yField": config.get("y_axis"),
                "smooth": True
            })
        elif chart_type == "pie":
            chart_config.update({
                "angleField": config.get("value"),
                "colorField": config.get("category")
            })
        elif chart_type == "scatter":
            chart_config.update({
                "xField": config.get("x_axis"),
                "yField": config.get("y_axis"),
                "size": 4
            })
        
        return {
            "success": True,
            "chart_config": chart_config
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@tool
def should_generate_chart(query: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    判断是否需要生成图表
    
    Args:
        query: 用户查询
        data: 查询结果数据
        
    Returns:
        是否需要生成图表的判断结果
    """
    try:
        # 检查数据是否适合可视化
        if not data or not isinstance(data, dict):
            return {
                "should_generate": False,
                "reason": "数据格式不正确或为空"
            }
        
        rows = data.get("rows", [])
        columns = data.get("columns", [])
        
        if not rows or not columns:
            return {
                "should_generate": False,
                "reason": "数据为空"
            }
        
        # 数据量检查
        if len(rows) < 2:
            return {
                "should_generate": False,
                "reason": "数据量太少，不适合生成图表"
            }
        
        if len(rows) > 1000:
            return {
                "should_generate": False,
                "reason": "数据量过大，建议先进行数据聚合"
            }
        
        # 查询意图分析
        query_lower = query.lower()
        visualization_keywords = [
            '图表', 'chart', '可视化', 'visualization', '图', 'graph',
            '趋势', 'trend', '分布', 'distribution', '比较', 'compare',
            '占比', 'percentage', '统计', 'statistics'
        ]
        
        has_viz_intent = any(keyword in query_lower for keyword in visualization_keywords)
        
        # 数据类型检查
        has_numeric_data = False
        if rows:
            first_row = rows[0]
            for value in first_row:
                if isinstance(value, (int, float)):
                    has_numeric_data = True
                    break
        
        if has_viz_intent or (has_numeric_data and len(columns) >= 2):
            return {
                "should_generate": True,
                "reason": "数据适合可视化且用户有可视化需求"
            }
        else:
            return {
                "should_generate": False,
                "reason": "用户查询主要关注数据内容，不需要图表可视化"
            }
        
    except Exception as e:
        return {
            "should_generate": False,
            "reason": f"判断过程出错: {str(e)}"
        }


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
        
        # 组合本地工具和包装后的MCP图表工具
        self.tools = [
            # analyze_data_for_chart,
            # generate_chart_config,
            # should_generate_chart
        ]
        
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
        
        return """你是一个专业的数据可视化专家。你的任务是：

1. 分析SQL查询结果数据的特征和结构
2. 判断是否需要生成图表
3. 推荐最适合的图表类型
4. 生成高质量的数据可视化图表

工作流程：
使用相应工具生成实际图表

请确保：
- 准确分析数据特征
- 选择最合适的图表类型
- 生成清晰美观的可视化效果
- 如果不适合生成图表，给出合理的解释

你需要根据用户查询意图和数据特点做出最佳的可视化决策。"""

    # 1.
    # 首先使用
    # should_generate_chart
    # 工具判断是否需要生成图表
    # 图表类型选择原则：
    # - 用户有明确要求
    # - 趋势分析：折线图(line
    # chart)
    # - 比较分析：柱状图(bar
    # chart)
    # - 占比分析：饼图(pie
    # chart)
    # - 相关性分析：散点图(scatter
    # plot)
    # - 复杂数据：表格(table)
    # - 其它合适格式的图表

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


# 2. 如果需要生成图表，使用 analyze_data_for_chart 工具分析数据特征
# 3. 使用 generate_chart_config 工具生成图表配置

# 创建全局实例
chart_generator_agent = ChartGeneratorAgent()
