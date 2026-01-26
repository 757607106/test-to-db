"""
图表生成智能体 (Chart Generator Agent)

职责：
1. 根据数据特征推荐合适的图表类型
2. 生成 Recharts 图表配置
3. 判断数据是否适合可视化

P2.2 升级: 意图驱动可视化
- 结合 analysis_intent 选择最合适的图表类型
- trend -> 折线图/面积图
- structure -> 饼图/堆叠图
- comparison -> 柱状图/分组柱状图
- correlation -> 散点图

与 Data Analyst Agent 的边界：
- Data Analyst: 负责数据解读和洞察生成（文本输出）
- Chart Generator: 负责图表配置和可视化建议（图表配置输出）

遵循 LangGraph 官方最佳实践:
- 使用 StreamWriter 进行流式输出
- 完全异步实现
"""
import json
import logging
import time
from typing import Dict, Any, List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import StreamWriter

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.schemas.stream_events import create_sql_step_event

logger = logging.getLogger(__name__)


# P2.2: 意图到图表类型的映射
INTENT_CHART_MAP = {
    "trend": ["line", "area"],           # 趋势分析 -> 折线图/面积图
    "structure": ["pie", "bar"],         # 结构分析 -> 饼图/柱状图
    "comparison": ["bar", "line"],       # 对比分析 -> 柱状图/折线图
    "correlation": ["scatter", "line"],  # 相关性分析 -> 散点图/折线图
    "detail": ["bar", "line"],           # 详情查看 -> 柱状图/折线图
    "summary": ["bar", "pie"],           # 综合汇总 -> 柱状图/饼图
}


class ChartGeneratorAgent:
    """
    图表生成智能体
    
    职责：
    - 分析数据结构，推荐图表类型
    - 生成 Recharts 兼容的图表配置
    - 判断是否需要图表可视化
    
    不负责：
    - 数据分析和洞察生成（由 DataAnalystAgent 处理）
    - SQL 生成或修正（由其他 Agent 处理）
    """
    
    def __init__(self, custom_prompt: str = None, llm=None):
        """
        初始化图表生成智能体
        
        Args:
            custom_prompt: 自定义系统提示词（可选）
            llm: 自定义 LLM 模型（可选）
        """
        self.name = "chart_generator_agent"
        self.custom_prompt = custom_prompt
        self.llm = llm or get_default_model()
    
    async def process(self, state: SQLMessageState, writer: StreamWriter = None) -> Dict[str, Any]:
        """
        处理图表生成任务
        
        遵循 LangGraph 官方最佳实践：
        - 使用 StreamWriter 参数注入
        - 支持流式输出
        
        Args:
            state: 当前状态
            writer: LangGraph StreamWriter（可选）
            
        Returns:
            状态更新字典，包含 chart_config
        """
        start_time = time.time()
        
        # 检查是否跳过图表生成
        if state.get("skip_chart_generation", False):
            logger.info("跳过图表生成（快速模式）")
            return {
                "current_stage": "completed",
                "chart_config": None
            }
        
        # 发送图表生成开始事件
        if writer:
            writer(create_sql_step_event(
                step="chart_generation",
                status="running",
                result="正在生成图表配置...",
                time_ms=0
            ))
        
        try:
            # 从状态中获取执行结果
            execution_result = state.get("execution_result")
            
            # 提取数据
            result_data = self._extract_result_data(execution_result)
            columns = result_data.get("columns", [])
            data = result_data.get("data", [])
            row_count = result_data.get("row_count", 0)
            
            # 判断是否适合生成图表
            if not self._should_generate_chart(columns, data, row_count):
                logger.info("数据不适合生成图表")
                return {
                    "current_stage": "completed",
                    "chart_config": None
                }
            
            # 生成图表配置
            chart_config = await self._generate_chart_config(columns, data, state)
            
            # 计算耗时
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # 发送图表生成完成事件
            if writer:
                writer(create_sql_step_event(
                    step="chart_generation",
                    status="completed",
                    result=f"图表配置生成完成: {chart_config.get('type', 'unknown')}",
                    time_ms=elapsed_ms
                ))
            
            logger.info(f"图表配置生成完成，类型: {chart_config.get('type')}, 耗时: {elapsed_ms}ms")
            
            return {
                "current_stage": "completed",
                "chart_config": chart_config
            }
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"图表生成失败: {e}")
            
            # 发送错误事件
            if writer:
                writer(create_sql_step_event(
                    step="chart_generation",
                    status="error",
                    result=str(e),
                    time_ms=elapsed_ms
                ))
            
            # 图表生成失败不影响整体流程
            return {
                "current_stage": "completed",
                "chart_config": None,
                "error_history": state.get("error_history", []) + [{
                    "stage": "chart_generation",
                    "error": str(e),
                    "retry_count": state.get("retry_count", 0)
                }]
            }
    
    def _extract_result_data(self, execution_result) -> Dict[str, Any]:
        """从执行结果中提取数据"""
        if not execution_result:
            return {"columns": [], "data": [], "row_count": 0}
        
        if hasattr(execution_result, 'data'):
            result_data = execution_result.data
        elif isinstance(execution_result, dict):
            result_data = execution_result.get("data", {})
        else:
            result_data = {}
        
        if isinstance(result_data, dict):
            return {
                "columns": result_data.get("columns", []),
                "data": result_data.get("data", []),
                "row_count": result_data.get("row_count", 0)
            }
        
        return {"columns": [], "data": [], "row_count": 0}
    
    def _should_generate_chart(self, columns: List[str], data: List, row_count: int) -> bool:
        """
        判断数据是否适合生成图表
        
        条件：
        - 至少有 2 列数据
        - 至少有 2 行数据
        - 数据行数不超过 100 行（过多数据图表不直观）
        """
        if len(columns) < 2:
            return False
        if row_count < 2:
            return False
        if row_count > 100:
            return False
        return True
    
    async def _generate_chart_config(
        self, 
        columns: List[str], 
        data: List,
        state: SQLMessageState
    ) -> Dict[str, Any]:
        """
        生成 Recharts 图表配置
        
        P2.2 升级: 支持意图驱动的图表选择
        
        策略：
        1. 首先检查 analysis_intent，优先使用意图推荐
        2. 然后使用规则推断图表类型
        3. 如果规则无法确定，使用 LLM 推荐
        """
        # 分析列类型
        column_types = self._analyze_column_types(columns, data)
        
        # P2.2: 获取分析意图
        analysis_intent = state.get("analysis_intent")
        
        # 规则推断图表类型（结合意图）
        chart_type = self._infer_chart_type(column_types, columns, data, analysis_intent)
        
        # 选择 X 轴和 Y 轴
        x_axis, y_axes = self._select_axes(column_types, columns)
        
        config = {
            "type": chart_type,
            "xAxis": x_axis,
            "yAxis": y_axes[0] if y_axes else x_axis,
            "dataKey": y_axes[0] if y_axes else columns[1] if len(columns) > 1 else columns[0],
            "xDataKey": x_axis,
            "series": [{"dataKey": y, "name": y} for y in y_axes[:3]],  # 最多3个系列
            "legend": len(y_axes) > 1
        }
        
        # P2.2: 添加意图信息到配置
        if analysis_intent:
            config["intent"] = analysis_intent
            logger.info(f"意图驱动图表选择: intent={analysis_intent} -> type={chart_type}")
        
        return config
    
    def _analyze_column_types(self, columns: List[str], data: List) -> Dict[str, str]:
        """
        分析列的数据类型
        
        返回：
        - numeric: 数值类型
        - category: 分类类型
        - date: 日期类型
        """
        column_types = {}
        
        if not data:
            return {col: "category" for col in columns}
        
        # 获取第一行数据用于类型推断
        first_row = data[0] if data else {}
        if isinstance(first_row, list) and len(first_row) == len(columns):
            first_row = dict(zip(columns, first_row))
        
        for col in columns:
            col_lower = col.lower()
            
            # 检测日期列
            if any(kw in col_lower for kw in ['date', 'time', '日期', '时间', 'day', 'month', 'year', '年', '月', '日']):
                column_types[col] = "date"
                continue
            
            # 检测分类列
            if any(kw in col_lower for kw in ['name', 'type', 'category', '名称', '类型', '分类', 'id', 'status', '状态']):
                column_types[col] = "category"
                continue
            
            # 检查数据值
            value = first_row.get(col) if isinstance(first_row, dict) else None
            if isinstance(value, (int, float)):
                column_types[col] = "numeric"
            else:
                column_types[col] = "category"
        
        return column_types
    
    def _infer_chart_type(
        self, 
        column_types: Dict[str, str], 
        columns: List[str],
        data: List,
        analysis_intent: Optional[str] = None
    ) -> str:
        """
        基于规则推断最合适的图表类型
        
        P2.2 升级: 支持意图驱动的图表选择
        
        优先级：
        1. 如果有 analysis_intent，优先使用意图推荐
        2. 然后根据数据特征进行规则推断
        """
        date_cols = [c for c, t in column_types.items() if t == "date"]
        numeric_cols = [c for c, t in column_types.items() if t == "numeric"]
        category_cols = [c for c, t in column_types.items() if t == "category"]
        
        row_count = len(data)
        
        # P2.2: 意图驱动的图表选择
        if analysis_intent and analysis_intent in INTENT_CHART_MAP:
            preferred_types = INTENT_CHART_MAP[analysis_intent]
            
            # 根据数据特征从推荐列表中选择最合适的
            for chart_type in preferred_types:
                if chart_type == "line" and (date_cols or row_count > 5):
                    return "line"
                if chart_type == "area" and date_cols:
                    return "area"
                if chart_type == "bar" and row_count <= 15:
                    return "bar"
                if chart_type == "pie" and row_count <= 8 and len(numeric_cols) >= 1:
                    return "pie"
                if chart_type == "scatter" and len(numeric_cols) >= 2:
                    return "scatter"
            
            # 如果没有完美匹配，使用推荐列表的第一个
            logger.info(f"意图 {analysis_intent} 推荐图表: {preferred_types[0]}")
            return preferred_types[0]
        
        # 原有规则推断逻辑
        # 有日期列 → 折线图
        if date_cols and numeric_cols:
            return "line"
        
        # 分类少于 8 个 → 柱状图
        if category_cols and numeric_cols and row_count <= 8:
            return "bar"
        
        # 只有一个数值列且分类少于 6 个 → 饼图
        if len(numeric_cols) == 1 and category_cols and row_count <= 6:
            return "pie"
        
        # 数据较多 → 折线图
        if row_count > 15:
            return "line"
        
        # 默认柱状图
        return "bar"
    
    def _select_axes(
        self, 
        column_types: Dict[str, str], 
        columns: List[str]
    ) -> tuple:
        """
        选择 X 轴和 Y 轴
        
        返回：(x_axis, [y_axes])
        """
        date_cols = [c for c, t in column_types.items() if t == "date"]
        numeric_cols = [c for c, t in column_types.items() if t == "numeric"]
        category_cols = [c for c, t in column_types.items() if t == "category"]
        
        # X 轴选择优先级：日期 > 分类 > 第一列
        if date_cols:
            x_axis = date_cols[0]
        elif category_cols:
            x_axis = category_cols[0]
        else:
            x_axis = columns[0]
        
        # Y 轴选择数值列
        y_axes = [c for c in numeric_cols if c != x_axis]
        
        # 如果没有数值列，选择非 X 轴的列
        if not y_axes:
            y_axes = [c for c in columns if c != x_axis]
        
        return x_axis, y_axes
    
    async def generate_chart(self, state: SQLMessageState) -> Dict[str, Any]:
        """生成图表（保留原有方法，向后兼容）"""
        return await self.process(state)


# 创建全局实例
chart_generator_agent = ChartGeneratorAgent()
