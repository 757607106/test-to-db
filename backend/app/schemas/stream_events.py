"""
流式事件类型定义

用于 LangGraph custom streaming mode 的事件数据结构
前端通过 onCustomEvent 接收这些事件

使用方法 (后端节点中):
    from langgraph.config import get_stream_writer
    writer = get_stream_writer()
    writer(IntentAnalysisEvent(...).model_dump())

事件类型:
- intent_analysis: 意图解析完成
- cache_hit: 缓存命中（thread_history/exact/semantic）
- sql_step: SQL生成各步骤
- data_query: 数据查询结果
- similar_questions: 相似问题推荐
- insight: 数据洞察分析结果
"""
from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field


class CacheHitEvent(BaseModel):
    """
    缓存命中事件 - 展示缓存命中信息
    
    hit_type 类型:
    - thread_history: 同一对话内历史命中
    - exact: 全局缓存精确匹配
    - semantic: 全局缓存语义匹配 (>=95%)
    """
    type: Literal["cache_hit"] = "cache_hit"
    hit_type: Literal["thread_history", "exact", "semantic"] = Field(description="命中类型")
    similarity: float = Field(default=1.0, description="相似度 (0-1)")
    original_query: Optional[str] = Field(default=None, description="原始匹配的查询")
    time_ms: int = Field(default=0, description="耗时(毫秒)")


class IntentAnalysisEvent(BaseModel):
    """意图解析事件 - 展示用户查询的解析结果"""
    type: Literal["intent_analysis"] = "intent_analysis"
    dataset: str = Field(description="数据集名称")
    query_mode: str = Field(description="查询模式: 聚合模式/明细模式")
    metrics: List[str] = Field(default_factory=list, description="指标列表")
    filters: Dict[str, Any] = Field(default_factory=dict, description="筛选条件")
    time_ms: int = Field(default=0, description="耗时(毫秒)")


class SQLStepEvent(BaseModel):
    """SQL生成步骤事件 - 展示SQL生成的各个步骤"""
    type: Literal["sql_step"] = "sql_step"
    step: str = Field(description="步骤名称: schema_mapping | few_shot | llm_parse | sql_fix | final_sql")
    status: str = Field(description="步骤状态: pending | running | completed | error")
    result: Optional[str] = Field(default=None, description="步骤结果")
    time_ms: int = Field(default=0, description="耗时(毫秒)")


class DataQueryEvent(BaseModel):
    """数据查询事件 - 展示查询结果数据"""
    type: Literal["data_query"] = "data_query"
    columns: List[str] = Field(default_factory=list, description="列名列表")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="数据行")
    row_count: int = Field(default=0, description="总行数")
    chart_config: Optional[Dict[str, Any]] = Field(default=None, description="Recharts 图表配置")
    title: Optional[str] = Field(default=None, description="数据标题")


class SimilarQuestionsEvent(BaseModel):
    """相似问题事件 - 展示推荐的相似问题"""
    type: Literal["similar_questions"] = "similar_questions"
    questions: List[str] = Field(default_factory=list, description="相似问题列表")


class InsightItem(BaseModel):
    """单个洞察项"""
    type: Literal["trend", "anomaly", "metric", "comparison"] = Field(description="洞察类型")
    description: str = Field(description="洞察描述")


class InsightEvent(BaseModel):
    """
    数据洞察事件 - 展示 AI 分析的业务洞察
    
    包含:
    - summary: 一句话摘要
    - insights: 结构化洞察列表 (趋势/异常/指标/对比)
    - recommendations: 业务建议列表
    """
    type: Literal["insight"] = "insight"
    summary: str = Field(description="一句话摘要")
    insights: List[InsightItem] = Field(default_factory=list, description="结构化洞察列表")
    recommendations: List[str] = Field(default_factory=list, description="业务建议列表")
    raw_content: Optional[str] = Field(default=None, description="原始 Markdown 内容")
    time_ms: int = Field(default=0, description="分析耗时(毫秒)")


# 辅助函数
def create_intent_analysis_event(
    dataset: str = "默认数据集",
    query_mode: str = "明细模式",
    metrics: List[str] = None,
    filters: Dict[str, Any] = None,
    time_ms: int = 0
) -> Dict[str, Any]:
    """创建意图解析事件"""
    return IntentAnalysisEvent(
        dataset=dataset,
        query_mode=query_mode,
        metrics=metrics or [],
        filters=filters or {},
        time_ms=time_ms
    ).model_dump()


def create_sql_step_event(
    step: str,
    status: str,
    result: Optional[str] = None,
    time_ms: int = 0
) -> Dict[str, Any]:
    """创建SQL步骤事件"""
    return SQLStepEvent(
        step=step,
        status=status,
        result=result,
        time_ms=time_ms
    ).model_dump()


def create_data_query_event(
    columns: List[str],
    rows: List[Dict[str, Any]],
    row_count: int,
    chart_config: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """创建数据查询事件"""
    return DataQueryEvent(
        columns=columns,
        rows=rows,
        row_count=row_count,
        chart_config=chart_config,
        title=title
    ).model_dump()


def create_similar_questions_event(
    questions: List[str]
) -> Dict[str, Any]:
    """创建相似问题事件"""
    return SimilarQuestionsEvent(
        questions=questions
    ).model_dump()


def create_cache_hit_event(
    hit_type: Literal["thread_history", "exact", "semantic"],
    similarity: float = 1.0,
    original_query: Optional[str] = None,
    time_ms: int = 0
) -> Dict[str, Any]:
    """
    创建缓存命中事件
    
    Args:
        hit_type: 命中类型
            - thread_history: 同一对话内历史命中
            - exact: 全局缓存精确匹配
            - semantic: 全局缓存语义匹配
        similarity: 相似度 (0-1)
        original_query: 原始匹配的查询
        time_ms: 耗时(毫秒)
    """
    return CacheHitEvent(
        hit_type=hit_type,
        similarity=similarity,
        original_query=original_query,
        time_ms=time_ms
    ).model_dump()


def create_insight_event(
    summary: str,
    insights: List[Dict[str, str]] = None,
    recommendations: List[str] = None,
    raw_content: Optional[str] = None,
    time_ms: int = 0
) -> Dict[str, Any]:
    """
    创建数据洞察事件
    
    Args:
        summary: 一句话摘要
        insights: 结构化洞察列表，每项包含 type 和 description
            - type: trend | anomaly | metric | comparison
            - description: 洞察描述
        recommendations: 业务建议列表
        raw_content: 原始 Markdown 内容
        time_ms: 分析耗时(毫秒)
    """
    insight_items = []
    if insights:
        for item in insights:
            insight_items.append(InsightItem(
                type=item.get("type", "metric"),
                description=item.get("description", "")
            ))
    
    return InsightEvent(
        summary=summary,
        insights=insight_items,
        recommendations=recommendations or [],
        raw_content=raw_content,
        time_ms=time_ms
    ).model_dump()
