"""
数据分析专家智能体 (Data Analyst Agent)

职责：
1. 分析 SQL 执行结果，提取关键洞察
2. 识别数据模式、趋势和异常
3. 生成自然语言的数据解读
4. 提供业务建议

与 Chart Generator Agent 的边界：
- Data Analyst: 负责数据解读和洞察生成（文本输出）
- Chart Generator: 负责图表配置和可视化建议（图表配置输出）

遵循 LangGraph 官方最佳实践:
- 使用 StreamWriter 进行流式输出
- 完全异步实现
- 支持 langgraph_supervisor 集成
"""
import json
import logging
import re
import time
from typing import Dict, Any, Optional, List

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.types import StreamWriter

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.core.agent_config import get_agent_llm, CORE_AGENT_CHART_ANALYST
from app.core.llm_wrapper import LLMWrapper, LLMWrapperConfig
from app.schemas.stream_events import create_sql_step_event, create_insight_event, create_stage_message_event
from app.agents.nodes.base import ErrorStage

logger = logging.getLogger(__name__)


# ============================================================================
# Tool 定义（用于 ReAct Agent）
# ============================================================================

@tool
def analyze_query_results(
    user_query: str,
    sql_query: str,
    columns: List[str],
    data: List[Dict[str, Any]],
    row_count: int
) -> Dict[str, Any]:
    """
    分析 SQL 查询结果，生成数据洞察和业务建议。
    
    Args:
        user_query: 用户原始查询
        sql_query: 执行的 SQL 语句
        columns: 结果列名
        data: 查询结果数据（字典列表）
        row_count: 总行数
    
    Returns:
        分析结果，包含摘要、洞察和建议
    """
    if not data:
        return {
            "summary": "查询结果为空",
            "insights": [],
            "recommendations": ["请检查查询条件是否过于严格", "确认数据是否已录入"]
        }
    
    # 预计算统计信息
    stats = _compute_statistics(columns, data)
    
    return {
        "summary": f"查询返回 {row_count} 条记录",
        "statistics": stats,
        "insights": [],
        "recommendations": [],
        "status": "需要 LLM 进一步分析"
    }


def _compute_statistics(columns: List[str], data: List[Dict]) -> Dict[str, Any]:
    """计算基础统计信息"""
    stats = {}
    for col in columns:
        values = [row.get(col) for row in data if row.get(col) is not None]
        if not values:
            continue
        
        # 尝试数值统计
        numeric_values = []
        for v in values:
            try:
                if isinstance(v, (int, float)):
                    numeric_values.append(float(v))
            except (ValueError, TypeError):
                pass
        
        if len(numeric_values) > len(values) * 0.5:
            stats[col] = {
                "type": "numeric",
                "min": min(numeric_values),
                "max": max(numeric_values),
                "avg": sum(numeric_values) / len(numeric_values)
            }
        else:
            # 分类统计
            unique_count = len(set(str(v) for v in values))
            stats[col] = {
                "type": "categorical",
                "unique_count": unique_count
            }
    
    return stats


class DataAnalystAgent:
    """
    数据分析专家智能体
    
    职责：
    - 分析 SQL 查询结果
    - 生成数据洞察和业务建议
    - 输出自然语言的分析报告
    
    不负责：
    - 图表配置生成（由 ChartGeneratorAgent 处理）
    - SQL 生成或修正（由其他 Agent 处理）
    """
    
    def __init__(self, custom_prompt: str = None, llm=None):
        """
        初始化数据分析专家
        
        Args:
            custom_prompt: 自定义系统提示词（用于自定义智能体）
            llm: 自定义 LLM 模型
        """
        self.name = "data_analyst_agent"
        self.custom_prompt = custom_prompt
        
        # 获取原生 LLM（用于 create_react_agent）
        raw_llm = llm or get_agent_llm(CORE_AGENT_CHART_ANALYST)
        
        # 创建 LLMWrapper（用于直接调用，统一重试和超时）
        if isinstance(raw_llm, LLMWrapper):
            self.llm = raw_llm
            # 如果传入的是 wrapper，获取底层 LLM 给 react agent
            self._raw_llm = raw_llm.llm
        else:
            self.llm = LLMWrapper(llm=raw_llm, name=self.name)
            self._raw_llm = raw_llm
        
        self.tools = [analyze_query_results]
        
        # 创建 LangGraph ReAct Agent（使用自定义 state_schema 以支持 connection_id 等字段）
        self.agent = create_react_agent(
            model=self._raw_llm,
            tools=self.tools,
            prompt=self._get_agent_prompt(),
            name="data_analyst_agent",
            state_schema=SQLMessageState,
        )

    def _get_agent_prompt(self) -> str:
        """获取 Agent 系统提示（用于 ReAct Agent）"""
        base_prompt = self._create_system_prompt()
        return f"""{base_prompt}

你是数据分析专家，负责分析 SQL 查询结果并生成洞察。
当收到查询结果时，使用 analyze_query_results 工具进行分析，然后基于分析结果生成详细的数据解读。
"""
    
    def _create_system_prompt(self) -> str:
        """
        创建系统提示词 - 升级版
        增强分析维度：趋势、异常、指标、对比
        """
        if self.custom_prompt:
            return self.custom_prompt
        
        return """你是一位具备深厚业务背景的商业分析师，负责解读 SQL 查询结果并提供有价值的业务洞察。

**分析维度** (请从以下维度进行分析，选择适用的):
1. 关键指标 (Key Metrics): 识别数据中的极值（最大/最小）、平均水平、总量、占比
2. 趋势识别 (Trends): 如果数据包含时间维度，分析增长、下降或周期性波动
3. 异常发现 (Anomalies): 识别偏离正常水平较大的数据点或异常模式
4. 对比分析 (Comparisons): 不同类别、时间段或维度之间的显著差异

**输出格式** (必须严格遵守此格式):

### 摘要
[一句话直接回答用户问题，包含关键数字]

### 核心洞察
- 趋势: [如有时间维度，描述趋势变化，否则跳过此项]
- 异常: [如发现异常数据点，描述异常，否则跳过此项]
- 指标: [关键指标的解读，如总量、平均值、极值等]
- 对比: [如有分类维度，描述不同类别间的差异，否则跳过此项]

### 业务建议
1. [基于数据的可行建议1]
2. [基于数据的可行建议2]

**注意事项**:
- 洞察必须基于数据事实，不要臆测
- 如果数据为空，分析可能的原因（时间范围过窄、筛选条件过严、数据尚未录入等）
- 保持简洁专业，每个洞察点控制在 1-2 句话
- 不要重复输出原始数据
- 不要生成图表配置（由图表专家处理）"""
    
    async def process(self, state: SQLMessageState, writer: StreamWriter = None) -> Dict[str, Any]:
        """
        处理数据分析任务
        
        遵循 LangGraph 官方最佳实践：
        - 使用 StreamWriter 参数注入（Python 3.11+）
        - 支持流式输出分析进度
        
        Args:
            state: 当前状态
            writer: LangGraph StreamWriter（可选）
            
        Returns:
            状态更新字典
        """
        start_time = time.time()
        
        # 发送分析开始事件
        if writer:
            writer(create_sql_step_event(
                step="data_analyst",
                status="running",
                result="正在分析数据...",
                time_ms=0
            ))
        
        try:
            # 从状态中获取执行结果
            execution_result = state.get("execution_result")
            generated_sql = state.get("generated_sql", "")
            
            # 获取用户原始查询
            user_query = self._extract_user_query(state)
            
            # 准备数据
            result_data = self._extract_result_data(execution_result)
            columns = result_data.get("columns", [])
            data = result_data.get("data", [])
            row_count = result_data.get("row_count", 0)
            
            # 预计算统计信息
            statistics = self._precompute_statistics(columns, data)
            
            # 限制数据量避免 token 过多
            data_preview = data[:20] if len(data) > 20 else data
            
            # 构建分析提示（包含统计信息）
            analysis_prompt = self._build_analysis_prompt(
                user_query=user_query,
                generated_sql=generated_sql,
                columns=columns,
                data_preview=data_preview,
                row_count=row_count,
                statistics=statistics
            )
            
            # 调用 LLM 进行分析
            response = await self.llm.ainvoke([
                HumanMessage(content=analysis_prompt)
            ])
            
            analysis_content = response.content
            
            # 计算耗时
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # 解析结构化洞察
            structured_insights = self._parse_structured_insights(analysis_content)
            
            # 发送分析完成事件（sql_step 类型，用于进度显示）
            if writer:
                writer(create_sql_step_event(
                    step="data_analyst",
                    status="completed",
                    result=structured_insights.get("summary", analysis_content[:200]),
                    time_ms=elapsed_ms
                ))
                
                # 发送结构化洞察事件（insight 类型，用于洞察展示）
                writer(create_insight_event(
                    summary=structured_insights.get("summary", ""),
                    insights=structured_insights.get("insights", []),
                    recommendations=structured_insights.get("recommendations", []),
                    raw_content=analysis_content,
                    time_ms=elapsed_ms
                ))
                stage_message = structured_insights.get("summary") or "分析完成，已生成洞察。"
                writer(create_stage_message_event(
                    message=f"分析完成：\n{stage_message}",
                    step="data_analyst",
                    time_ms=elapsed_ms
                ))
            
            # 构建分析洞察结构化数据（存入状态）
            analyst_insights = {
                "summary": structured_insights.get("summary", ""),
                "insights": structured_insights.get("insights", []),
                "recommendations": structured_insights.get("recommendations", []),
                "raw_content": analysis_content,
                "analysis_time_ms": elapsed_ms,
                "data_points": row_count,
                "columns_analyzed": len(columns),
                "statistics": statistics
            }
            
            logger.info(f"数据分析完成，耗时: {elapsed_ms}ms, 分析 {row_count} 条数据, 提取 {len(structured_insights.get('insights', []))} 个洞察")
            
            return {
                "messages": [AIMessage(content=analysis_content)],
                "analyst_insights": analyst_insights,
                "current_stage": "chart_generation",
                "needs_analysis": False
            }
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"数据分析失败: {e}")
            
            # 发送错误事件
            if writer:
                writer(create_sql_step_event(
                    step="data_analyst",
                    status="error",
                    result=str(e),
                    time_ms=elapsed_ms
                ))
            
            return {
                "messages": [AIMessage(content=f"数据分析遇到问题，但查询已成功执行。")],
                "current_stage": "chart_generation",
                "error_history": state.get("error_history", []) + [{
                    "stage": ErrorStage.DATA_ANALYSIS,
                    "error": str(e),
                    "retry_count": state.get("retry_count", 0)
                }]
            }
    
    def _extract_user_query(self, state: SQLMessageState) -> str:
        """从状态中提取用户原始查询"""
        # 优先使用已保存的原始查询
        if state.get("original_query"):
            return state["original_query"]
        
        if state.get("enriched_query"):
            return state["enriched_query"]
        
        # 从消息中提取（取最后一个 HumanMessage）
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                content = msg.content
                if isinstance(content, list):
                    content = content[0].get("text", "") if content else ""
                return content
        return ""
    
    def _extract_result_data(self, execution_result) -> Dict[str, Any]:
        """从执行结果中提取数据"""
        if not execution_result:
            logger.warning("execution_result 为空")
            return {"columns": [], "data": [], "row_count": 0}
        
        # 支持 SQLExecutionResult 对象
        if hasattr(execution_result, 'data'):
            result_data = execution_result.data
            logger.debug(f"从 SQLExecutionResult 提取数据, data 类型: {type(result_data)}")
        elif isinstance(execution_result, dict):
            result_data = execution_result.get("data", {})
            logger.debug(f"从 dict 提取数据, data 类型: {type(result_data)}")
        else:
            logger.warning(f"未知的 execution_result 类型: {type(execution_result)}")
            result_data = {}
        
        if isinstance(result_data, dict):
            columns = result_data.get("columns", [])
            raw_data = result_data.get("data", [])
            row_count = result_data.get("row_count", 0)
            
            # 如果 row_count 为 0 但 raw_data 有数据，使用 raw_data 的长度
            if row_count == 0 and raw_data:
                row_count = len(raw_data)
                logger.info(f"row_count 为0但数据非空，使用实际数据长度: {row_count}")
            
            logger.info(f"数据提取完成: columns={len(columns)}, raw_data={len(raw_data)}, row_count={row_count}")
            
            # 将值列表转换为字典列表（如果需要）
            data = []
            for row in raw_data:
                if isinstance(row, list) and len(row) == len(columns):
                    # 值列表格式 -> 转换为字典
                    data.append(dict(zip(columns, row)))
                elif isinstance(row, dict):
                    # 已经是字典格式
                    data.append(row)
                else:
                    # 其他格式，跳过
                    continue
            
            return {
                "columns": columns,
                "data": data,
                "row_count": row_count
            }
        
        logger.warning(f"result_data 不是字典类型: {type(result_data)}")
        return {"columns": [], "data": [], "row_count": 0}
    
    def _precompute_statistics(self, columns: List[str], data: List[Dict]) -> Dict[str, Any]:
        """
        预计算统计指标，为 LLM 提供上下文
        
        Args:
            columns: 列名列表
            data: 数据行列表
            
        Returns:
            统计信息字典
        """
        stats = {
            "numeric_columns": [],
            "categorical_columns": [],
            "date_columns": [],
            "statistics": {}
        }
        
        if not data or not columns:
            return stats
        
        # 识别列类型并计算统计
        for col in columns:
            values = [row.get(col) for row in data if row.get(col) is not None]
            if not values:
                continue
            
            # 检测数值列
            numeric_values = []
            for v in values:
                try:
                    if isinstance(v, (int, float)):
                        numeric_values.append(float(v))
                    elif isinstance(v, str) and v.replace('.', '').replace('-', '').isdigit():
                        numeric_values.append(float(v))
                except (ValueError, TypeError):
                    pass
            
            if len(numeric_values) > len(values) * 0.8:  # 80%+ 是数值
                stats["numeric_columns"].append(col)
                if numeric_values:
                    stats["statistics"][col] = {
                        "min": min(numeric_values),
                        "max": max(numeric_values),
                        "avg": sum(numeric_values) / len(numeric_values),
                        "sum": sum(numeric_values)
                    }
            else:
                # 检测日期列
                date_keywords = ["date", "time", "日期", "时间", "created", "updated"]
                if any(kw in col.lower() for kw in date_keywords):
                    stats["date_columns"].append(col)
                else:
                    stats["categorical_columns"].append(col)
                    # 统计分类值分布
                    value_counts = {}
                    for v in values:
                        v_str = str(v)
                        value_counts[v_str] = value_counts.get(v_str, 0) + 1
                    stats["statistics"][col] = {
                        "unique_count": len(value_counts),
                        "top_values": sorted(value_counts.items(), key=lambda x: -x[1])[:5]
                    }
        
        return stats
    
    def _parse_structured_insights(self, content: str) -> Dict[str, Any]:
        """
        从 Markdown 内容中提取结构化洞察
        
        Args:
            content: LLM 返回的 Markdown 内容
            
        Returns:
            结构化的洞察数据
        """
        result = {
            "summary": "",
            "insights": [],
            "recommendations": [],
            "raw_content": content
        }
        
        # 提取摘要 - 支持多种格式: 摘要/数据摘要/回答/总结
        summary_match = re.search(r'###\s*(?:数据)?摘要\s*\n(.*?)(?=\n###|\n\n###|$)', content, re.DOTALL)
        if summary_match:
            result["summary"] = summary_match.group(1).strip()
        else:
            # 兼容旧格式 "### 回答" 或 "### 总结"
            answer_match = re.search(r'###\s*(?:回答|总结)\s*\n(.*?)(?=\n###|\n\n###|$)', content, re.DOTALL)
            if answer_match:
                result["summary"] = answer_match.group(1).strip()
        
        # 提取洞察
        insights_match = re.search(r'###\s*核心洞察\s*\n(.*?)(?=\n###|\n\n###|$)', content, re.DOTALL)
        if not insights_match:
            insights_match = re.search(r'###\s*数据洞察\s*\n(.*?)(?=\n###|\n\n###|$)', content, re.DOTALL)
        
        if insights_match:
            insights_text = insights_match.group(1)
            # 解析各类型洞察 - 支持多种格式
            # 格式1: **趋势**: 描述
            # 格式2: **趋势 (Trend)**: 描述
            insight_patterns = [
                (r'\*\*趋势(?:\s*\([^)]+\))?\*\*[：:]\s*(.*?)(?=\n-\s*\*\*|$)', "trend"),
                (r'\*\*异常(?:\s*\([^)]+\))?\*\*[：:]\s*(.*?)(?=\n-\s*\*\*|$)', "anomaly"),
                (r'\*\*指标(?:\s*\([^)]+\))?\*\*[：:]\s*(.*?)(?=\n-\s*\*\*|$)', "metric"),
                (r'\*\*对比(?:\s*\([^)]+\))?\*\*[：:]\s*(.*?)(?=\n-\s*\*\*|$)', "comparison"),
            ]
            
            for pattern, insight_type in insight_patterns:
                match = re.search(pattern, insights_text, re.DOTALL)
                if match:
                    description = match.group(1).strip()
                    if description and description not in ["无", "N/A", "-", "跳过"]:
                        result["insights"].append({
                            "type": insight_type,
                            "description": description
                        })
            
            # 如果没有匹配到结构化洞察，尝试解析列表格式
            if not result["insights"]:
                list_items = re.findall(r'[-\d.]\s*[.、]?\s*(.+)', insights_text)
                for item in list_items:
                    item = item.strip()
                    if item and not item.startswith("**"):
                        result["insights"].append({
                            "type": "metric",
                            "description": item
                        })
        
        # 提取建议
        recommendations_match = re.search(r'###\s*(?:业务)?建议\s*\n(.*?)(?=\n###|$)', content, re.DOTALL)
        if recommendations_match:
            rec_text = recommendations_match.group(1)
            # 解析列表项
            rec_items = re.findall(r'[-\d.]\s*[.、]?\s*(.+)', rec_text)
            for item in rec_items:
                item = item.strip()
                if item:
                    result["recommendations"].append(item)
        
        return result
    
    def _build_analysis_prompt(
        self,
        user_query: str,
        generated_sql: str,
        columns: List[str],
        data_preview: List,
        row_count: int,
        statistics: Dict[str, Any] = None
    ) -> str:
        """构建分析提示，包含预计算的统计信息"""
        # 格式化数据预览
        data_str = json.dumps(data_preview, ensure_ascii=False, default=str)
        
        # 格式化统计信息
        stats_str = ""
        if statistics:
            if statistics.get("numeric_columns"):
                stats_str += f"\n- 数值列: {', '.join(statistics['numeric_columns'])}"
            if statistics.get("date_columns"):
                stats_str += f"\n- 日期列: {', '.join(statistics['date_columns'])}"
            if statistics.get("categorical_columns"):
                stats_str += f"\n- 分类列: {', '.join(statistics['categorical_columns'])}"
            if statistics.get("statistics"):
                stats_str += "\n- 统计摘要:"
                for col, stat in statistics["statistics"].items():
                    if "avg" in stat:
                        stats_str += f"\n  - {col}: 最小={stat['min']:.2f}, 最大={stat['max']:.2f}, 平均={stat['avg']:.2f}, 总和={stat['sum']:.2f}"
                    elif "unique_count" in stat:
                        top_vals = ", ".join([f"{v[0]}({v[1]})" for v in stat.get("top_values", [])[:3]])
                        stats_str += f"\n  - {col}: {stat['unique_count']}个唯一值, TOP3: {top_vals}"
        
        return f"""{self._create_system_prompt()}

---

**用户问题**: {user_query}

**查询结果**:
- 列名: {columns}
- 数据行数: {row_count}
- 数据内容（最多20行）: {data_str}
{stats_str if stats_str else ""}

请根据以上数据进行分析，直接回答用户问题："""


# 创建全局实例
data_analyst_agent = DataAnalystAgent()

__all__ = [
    "DataAnalystAgent",
    "data_analyst_agent",
]
