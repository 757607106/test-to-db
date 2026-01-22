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
"""
import json
import logging
import time
from typing import Dict, Any, Optional, List

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import StreamWriter

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.schemas.stream_events import create_sql_step_event

logger = logging.getLogger(__name__)


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
        self.llm = llm or get_default_model()
    
    def _create_system_prompt(self) -> str:
        """
        创建系统提示词
        """
        if self.custom_prompt:
            return self.custom_prompt
        
        return """你是一位专业的数据分析专家，负责解读 SQL 查询结果并提供有价值的洞察。

**核心职责**:
1. 直接回答用户的问题
2. 分析数据中的关键发现
3. 识别数据模式、趋势和异常
4. 提供可行的业务建议

**输出要求**:
- 首先直接回答用户的问题（一句话概括）
- 然后提供 2-3 个关键数据洞察
- 最后给出 1-2 条业务建议（如果适用）

**输出格式**:
### 回答
[直接回答用户问题]

### 数据洞察
1. [洞察1]
2. [洞察2]
...

### 建议
- [建议1]
- [建议2]

**注意事项**:
- 保持简洁专业，避免冗长
- 如果数据为空，分析可能的原因
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
                step="data_analysis",
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
            
            # 限制数据量避免 token 过多
            data_preview = data[:20] if len(data) > 20 else data
            
            # 构建分析提示
            analysis_prompt = self._build_analysis_prompt(
                user_query=user_query,
                generated_sql=generated_sql,
                columns=columns,
                data_preview=data_preview,
                row_count=row_count
            )
            
            # 调用 LLM 进行分析
            response = await self.llm.ainvoke([
                HumanMessage(content=analysis_prompt)
            ])
            
            analysis_content = response.content
            
            # 计算耗时
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # 发送分析完成事件
            if writer:
                writer(create_sql_step_event(
                    step="data_analysis",
                    status="completed",
                    result=f"数据分析完成",
                    time_ms=elapsed_ms
                ))
            
            # 构建分析洞察结构化数据
            analyst_insights = {
                "summary": analysis_content,
                "analysis_time_ms": elapsed_ms,
                "data_points": row_count,
                "columns_analyzed": len(columns)
            }
            
            logger.info(f"数据分析完成，耗时: {elapsed_ms}ms, 分析 {row_count} 条数据")
            
            return {
                "messages": [AIMessage(content=analysis_content)],
                "analyst_insights": analyst_insights,
                "current_stage": "chart_generation",  # 下一阶段：图表生成
                "needs_analysis": False
            }
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"数据分析失败: {e}")
            
            # 发送错误事件
            if writer:
                writer(create_sql_step_event(
                    step="data_analysis",
                    status="error",
                    result=str(e),
                    time_ms=elapsed_ms
                ))
            
            return {
                "messages": [AIMessage(content=f"数据分析遇到问题，但查询已成功执行。")],
                "current_stage": "chart_generation",  # 继续到图表生成
                "error_history": state.get("error_history", []) + [{
                    "stage": "data_analysis",
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
        
        # 从消息中提取
        messages = state.get("messages", [])
        for msg in messages:
            if hasattr(msg, 'type') and msg.type == 'human':
                content = msg.content
                if isinstance(content, list):
                    content = content[0].get("text", "") if content else ""
                return content
        return ""
    
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
    
    def _build_analysis_prompt(
        self,
        user_query: str,
        generated_sql: str,
        columns: List[str],
        data_preview: List,
        row_count: int
    ) -> str:
        """构建分析提示"""
        # 格式化数据预览
        data_str = json.dumps(data_preview, ensure_ascii=False, default=str)
        
        return f"""{self._create_system_prompt()}

---

**用户问题**: {user_query}

**执行的 SQL**:
```sql
{generated_sql}
```

**查询结果**:
- 列名: {columns}
- 数据行数: {row_count}
- 数据内容（最多20行）: {data_str}

请根据以上信息进行分析："""


# 创建全局实例
data_analyst_agent = DataAnalystAgent()

__all__ = [
    "DataAnalystAgent",
    "data_analyst_agent",
]
