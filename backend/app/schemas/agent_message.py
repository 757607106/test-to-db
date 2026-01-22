"""
Agent消息统一格式定义

该模块定义了所有Agent工具返回的统一格式，确保前后端消息格式一致性。
基于 LangChain 原生结构化输出方案。
"""
from typing import Literal, Optional, Any, Dict
from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    """
    统一的工具返回格式
    
    所有Agent工具必须返回此格式，确保前端解析的一致性。
    
    Attributes:
        status: 执行状态 - "success" (成功), "error" (错误), "pending" (待处理)
        data: 成功时的数据负载，可以是任意类型
        error: 错误消息，仅在 status="error" 时使用
        metadata: 附加元数据（如执行时间、缓存信息等）
        
    Examples:
        >>> # 成功响应
        >>> ToolResponse(
        ...     status="success",
        ...     data={"columns": ["id", "name"], "rows": [[1, "Alice"]]},
        ...     metadata={"execution_time": 0.5, "from_cache": False}
        ... )
        
        >>> # 错误响应
        >>> ToolResponse(
        ...     status="error",
        ...     error="数据库连接失败",
        ...     metadata={"connection_id": 123}
        ... )
        
        >>> # 待处理响应
        >>> ToolResponse(
        ...     status="pending",
        ...     metadata={"estimated_time": 5}
        ... )
    """
    status: Literal["success", "error", "pending"] = Field(
        description="执行状态：success=成功, error=错误, pending=待处理"
    )
    data: Optional[Any] = Field(
        default=None,
        description="成功时的数据负载"
    )
    error: Optional[str] = Field(
        default=None,
        description="错误信息（仅当 status='error' 时使用）"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="附加元数据（execution_time、cache_info、row_count等）"
    )
    
    def __str__(self) -> str:
        """
        返回 JSON 格式字符串
        
        LangChain @tool 装饰器会调用 str() 将返回值转换为字符串。
        我们重写 __str__ 确保返回的是 JSON 格式而不是 Python repr 格式。
        这对于前端解析工具结果至关重要。
        """
        return self.model_dump_json()
    
    class Config:
        """Pydantic 配置"""
        json_schema_extra = {
            "examples": [
                {
                    "status": "success",
                    "data": {
                        "columns": ["id", "name", "email"],
                        "rows": [
                            [1, "Alice", "alice@example.com"],
                            [2, "Bob", "bob@example.com"]
                        ]
                    },
                    "metadata": {
                        "execution_time": 0.5,
                        "row_count": 2,
                        "from_cache": False
                    }
                },
                {
                    "status": "error",
                    "error": "找不到连接ID为 999 的数据库连接",
                    "metadata": {
                        "connection_id": 999
                    }
                },
                {
                    "status": "pending",
                    "metadata": {
                        "message": "查询正在执行中，请稍后重试"
                    }
                }
            ]
        }


class SQLGenerationResult(BaseModel):
    """
    SQL生成结果的结构化输出格式
    
    用于 with_structured_output，确保跨模型（GPT-4/DeepSeek/Llama）生成一致的SQL格式。
    
    Attributes:
        sql_query: 生成的SQL语句
        explanation: SQL解释说明（可选）
        confidence: 生成置信度（0-1之间）
        
    Examples:
        >>> SQLGenerationResult(
        ...     sql_query="SELECT * FROM users WHERE age > 18 LIMIT 100",
        ...     explanation="查询年龄大于18岁的用户，限制返回100条",
        ...     confidence=0.95
        ... )
    """
    sql_query: str = Field(
        description="生成的SQL查询语句"
    )
    explanation: Optional[str] = Field(
        default=None,
        description="SQL语句的解释说明"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="生成的置信度（0-1之间，1表示非常有信心）"
    )
    
    class Config:
        """Pydantic 配置"""
        json_schema_extra = {
            "examples": [
                {
                    "sql_query": "SELECT name, COUNT(*) as order_count FROM orders GROUP BY name ORDER BY order_count DESC LIMIT 10",
                    "explanation": "统计每个用户的订单数量，按订单数降序排列，返回前10名",
                    "confidence": 0.92
                }
            ]
        }
