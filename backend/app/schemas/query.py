from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    connection_id: int
    natural_language_query: str

class QueryResponse(BaseModel):
    sql: str
    results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    context: Optional[Dict[str, Any]] = None  # For debugging/explanation


# 新增：多轮对话和分析相关的Schema

class ClarificationQuestion(BaseModel):
    """澄清问题"""
    id: str
    question: str
    type: Literal["choice", "text"] = "text"
    options: Optional[List[str]] = None
    related_ambiguity: Optional[str] = None


class ClarificationResponse(BaseModel):
    """澄清回复"""
    question_id: str
    answer: str


class AnalystInsights(BaseModel):
    """分析师洞察"""
    summary: Optional[Dict[str, Any]] = None
    trends: Optional[Dict[str, Any]] = None
    anomalies: Optional[List[Dict[str, Any]]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    visualizations: Optional[List[str]] = None


class ChatQueryRequest(BaseModel):
    """聊天式查询请求（支持多轮对话）"""
    connection_id: int
    natural_language_query: str
    conversation_id: Optional[str] = None
    clarification_responses: Optional[List[ClarificationResponse]] = None


class ChatQueryResponse(BaseModel):
    """聊天式查询响应"""
    conversation_id: str
    needs_clarification: bool = False
    clarification_questions: Optional[List[ClarificationQuestion]] = None
    sql: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    analyst_insights: Optional[AnalystInsights] = None
    chart_config: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stage: Optional[str] = None  # 当前处理阶段
