from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
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
    agent_id: Optional[int] = None # Deprecated: use agent_ids
    agent_ids: Optional[List[int]] = None # New: support multiple agents


class ChatQueryResponse(BaseModel):
    """聊天式查询响应"""
    conversation_id: str
    message: Optional[str] = None # 通用文本回复
    needs_clarification: bool = False
    clarification_questions: Optional[List[ClarificationQuestion]] = None
    sql: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    analyst_insights: Optional[AnalystInsights] = None
    chart_config: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stage: Optional[str] = None  # 当前处理阶段


# ✅ Phase 2 新增: 会话管理Schema

class ConversationSummary(BaseModel):
    """会话摘要"""
    thread_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_query: Optional[str] = None
    status: str  # active, completed, error


class ConversationDetail(BaseModel):
    """会话详情"""
    thread_id: str
    created_at: datetime
    updated_at: datetime
    messages: List[Dict[str, Any]]
    states: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


# ✅ LangGraph interrupt/resume相关Schema

class ResumeQueryRequest(BaseModel):
    """恢复被interrupt暂停的查询 - LangGraph Command模式"""
    thread_id: str = Field(..., description="会话线程ID")
    user_response: Any = Field(..., description="用户对interrupt请求的回复")
    connection_id: int = Field(default=15, description="数据库连接ID")


class ResumeQueryResponse(BaseModel):
    """恢复查询的响应"""
    success: bool
    thread_id: str
    sql: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    chart_config: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stage: Optional[str] = None
