"""
混合检索服务 - 数据模型

包含:
- QAPairWithContext: 带上下文的问答对
- RetrievalResult: 检索结果
"""

from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class QAPairWithContext:
    """带上下文的问答对"""
    id: str
    question: str
    sql: str
    connection_id: int
    difficulty_level: int
    query_type: str
    success_rate: float
    verified: bool
    created_at: datetime

    # 上下文信息
    used_tables: List[str]
    used_columns: List[str]
    query_pattern: str
    mentioned_entities: List[str]

    # 向量表示
    embedding_vector: Optional[List[float]] = None


@dataclass
class RetrievalResult:
    """检索结果"""
    qa_pair: QAPairWithContext
    semantic_score: float = 0.0
    structural_score: float = 0.0
    pattern_score: float = 0.0
    quality_score: float = 0.0
    final_score: float = 0.0
    explanation: str = ""
