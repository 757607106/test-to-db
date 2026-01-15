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
from app.core.agent_config import get_agent_llm, CORE_AGENT_CHART_ANALYST
from app.core.config import settings

# 初始化MCP图表服务器客户端
def _initialize_chart_client():
    """初始化图表生成客户端"""
    try:
        # 检查 API Key 是否配置
        if not settings.DASHSCOPE_API_KEY:
            print("警告: 未配置 DASHSCOPE_API_KEY，将跳过 AntV 图表工具初始化")
            return None, []

        # 使用用户提供的阿里云 AntV MCP 配置
        client = MultiServerMCPClient(
            {
                "antv-visualization-chart": {
                    "transport": "sse",
                    "url": "https://dashscope.aliyuncs.com/api/v1/mcps/antv-visualization-chart/sse",
                    "headers": {
                        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}"
                    }
                }
            }
        )
        # 获取工具
        # 注意：这里是一个异步操作，但在模块级别我们需要同步获取，或者延迟加载
        # 为了简单起见，这里使用 asyncio.run，但在生产环境中最好在 agent 初始化时异步加载
        chart_tools = asyncio.run(client.get_tools())
        print(f"成功加载 AntV 图表工具: {len(chart_tools)} 个")
        return client, chart_tools
    except Exception as e:
        print(f"图表客户端初始化失败: {e}")
        return None, []

# 全局图表客户端和工具
CHART_CLIENT, CHART_TOOLS = _initialize_chart_client()

@tool
def analyze_data_for_chart(data: Dict[str, Any], query_context: str) -> Dict[str, Any]:
    """
    分析数据特征，确定最适合的图表类型
    
    Args:
        data: SQL查询结果数据
        query_context: 查询上下文信息
        
    Returns:
        图表类型建议和配置信息
    """
    try:
        if not data or not isinstance(data, dict):
            return {
                "success": False,
                "error": "无效的数据格式"
            }
        
        # 分析数据结构
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        
        if not columns or not rows:
            return {
                "success": False,
                "error": "数据为空或格式不正确"
            }
        
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
        
        return {
            "success": True,
            "data_analysis": {
                "total_columns": num_columns,
                "total_rows": num_rows,
                "numeric_columns": numeric_columns,
                "text_columns": text_columns,
                "date_columns": date_columns
            },
            "chart_recommendation": chart_recommendation
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

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
    
    def __init__(self):
        self.name = "chart_generator_agent"
        # 使用特定的核心配置
        self.llm = get_agent_llm(CORE_AGENT_CHART_ANALYST)
        
        # 组合本地工具和MCP图表工具
        self.tools = [
            analyze_data_for_chart,
            generate_chart_config,
            should_generate_chart
        ]
        
        # 如果MCP图表工具可用，添加到工具列表
        if CHART_TOOLS:
            self.tools.extend(CHART_TOOLS)
        
        # 创建ReAct代理
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self._create_system_prompt(),
            name=self.name
        )
    
    def _create_system_prompt(self) -> str:
        """创建系统提示"""
        return """你是一个专业的数据可视化专家。你的任务是：

1. 分析SQL查询结果数据的特征和结构
2. 判断是否需要生成图表
3. 推荐最适合的图表类型
4. 生成高质量的数据可视化图表

工作流程：
- 首先使用 should_generate_chart 判断
- 如果需要，使用 analyze_data_for_chart 分析
- 使用 MCP 提供的图表工具（如 create_chart 等）来生成图表
- 如果 MCP 工具不可用，使用 generate_chart_config 降级处理

请确保：
- 准确分析数据特征
- 选择最合适的图表类型
- 生成清晰美观的可视化效果
- 如果不适合生成图表，给出合理的解释

你需要根据用户查询意图和数据特点做出最佳的可视化决策。"""

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
