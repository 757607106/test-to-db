import os
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "development_secret_key")

    # CORS settings
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database settings
    MYSQL_SERVER: str = os.getenv("MYSQL_SERVER", "localhost")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "chatdb")
    MYSQL_PORT: str = os.getenv("MYSQL_PORT", "3306")

    # Neo4j settings
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

    # LLM settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE: Optional[str] = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")

    # ==========================================
    # Milvus 向量数据库配置
    # ==========================================
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT: str = os.getenv("MILVUS_PORT", "19530")

    # ==========================================
    # 向量模型配置（Fallback 机制）
    # ==========================================
    # ⚠️ 重要说明：
    # - 生产环境推荐在「管理后台 > 模型配置」页面设置 Embedding 模型
    # - 以下配置仅在以下情况作为 fallback 使用：
    #   1. 数据库未配置默认 Embedding 模型时
    #   2. 测试脚本直接实例化 VectorService 时
    #   3. 系统初始化或迁移脚本时
    # - 数据库配置优先级：数据库 > 环境变量 > 以下默认值
    # ==========================================
    
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:0.6b")
    VECTOR_DIMENSION: int = int(os.getenv("VECTOR_DIMENSION", "1024"))

    # Ollama 配置（本地部署）
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_EMBEDDING_MODEL: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b")  # Fallback
    OLLAMA_REQUEST_TIMEOUT: int = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "60"))
    OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "-1"))
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.0"))

    # 阿里云 DashScope 配置（云端API）
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_BASE_URL: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    DASHSCOPE_EMBEDDING_MODEL: str = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4")  # Fallback

    # 向量服务通用配置
    VECTOR_SERVICE_TYPE: str = os.getenv("VECTOR_SERVICE_TYPE", "aliyun")  # Fallback: ollama | aliyun（支持OpenAI兼容API）
    VECTOR_CACHE_ENABLED: bool = os.getenv("VECTOR_CACHE_ENABLED", "true").lower() == "true"
    VECTOR_CACHE_TTL: int = int(os.getenv("VECTOR_CACHE_TTL", "3600"))  # 缓存有效期（秒）
    VECTOR_BATCH_SIZE: int = int(os.getenv("VECTOR_BATCH_SIZE", "32"))  # 批处理大小
    VECTOR_MAX_RETRIES: int = int(os.getenv("VECTOR_MAX_RETRIES", "3"))  # 最大重试次数
    VECTOR_RETRY_DELAY: float = float(os.getenv("VECTOR_RETRY_DELAY", "1.0"))  # 重试延迟（秒）

    # ==========================================
    # 混合检索配置
    # ==========================================
    # 混合检索系统包含：语义检索（Milvus）+ 结构检索（Neo4j）+ 模式检索（Neo4j）
    # FusionRanker 会根据以下权重动态融合多个检索结果
    # ==========================================
    HYBRID_RETRIEVAL_ENABLED: bool = os.getenv("HYBRID_RETRIEVAL_ENABLED", "true").lower() == "true"
    
    # 融合权重配置（总和应为 1.0）
    SEMANTIC_WEIGHT: float = float(os.getenv("SEMANTIC_WEIGHT", "0.60"))      # 语义相似度权重（向量检索）
    STRUCTURAL_WEIGHT: float = float(os.getenv("STRUCTURAL_WEIGHT", "0.20"))  # 结构匹配权重（表结构）
    PATTERN_WEIGHT: float = float(os.getenv("PATTERN_WEIGHT", "0.10"))        # 模式匹配权重（查询类型）
    QUALITY_WEIGHT: float = float(os.getenv("QUALITY_WEIGHT", "0.10"))        # 质量评分权重（成功率、验证状态）

    # 学习配置
    AUTO_LEARNING_ENABLED: bool = os.getenv("AUTO_LEARNING_ENABLED", "true").lower() == "true"
    FEEDBACK_LEARNING_ENABLED: bool = os.getenv("FEEDBACK_LEARNING_ENABLED", "true").lower() == "true"
    PATTERN_DISCOVERY_ENABLED: bool = os.getenv("PATTERN_DISCOVERY_ENABLED", "true").lower() == "true"

    # 性能配置
    RETRIEVAL_CACHE_TTL: int = int(os.getenv("RETRIEVAL_CACHE_TTL", "3600"))
    MAX_EXAMPLES_PER_QUERY: int = int(os.getenv("MAX_EXAMPLES_PER_QUERY", "5"))
    PARALLEL_RETRIEVAL: bool = os.getenv("PARALLEL_RETRIEVAL", "true").lower() == "true"

    # ==========================================
    # QA样本智能召回配置
    # ==========================================
    # 用于SQL生成时自动检索相似的历史问答对，提升生成质量
    # 点赞的问答对会自动存储到智能训练中心，用于后续召回
    # ==========================================
    
    # 是否启用QA样本召回（关闭后SQL生成将不使用历史样本）
    QA_SAMPLE_ENABLED: bool = os.getenv("QA_SAMPLE_ENABLED", "true").lower() == "true"
    
    # 最小相似度阈值（0.0-1.0，低于此值的样本将被过滤）
    QA_SAMPLE_MIN_SIMILARITY: float = float(os.getenv("QA_SAMPLE_MIN_SIMILARITY", "0.6"))
    
    # 召回的样本数量（Top-K）
    QA_SAMPLE_TOP_K: int = int(os.getenv("QA_SAMPLE_TOP_K", "3"))
    
    # 检索超时时间（秒，避免阻塞查询）
    QA_SAMPLE_TIMEOUT: int = int(os.getenv("QA_SAMPLE_TIMEOUT", "10"))
    
    # 是否在没有样本时快速降级（true=快速跳过，false=等待完整检索）
    QA_SAMPLE_FAST_FALLBACK: bool = os.getenv("QA_SAMPLE_FAST_FALLBACK", "true").lower() == "true"
    
    # 样本质量过滤：只使用验证过的样本
    QA_SAMPLE_VERIFIED_ONLY: bool = os.getenv("QA_SAMPLE_VERIFIED_ONLY", "false").lower() == "true"
    
    # 样本质量过滤：最低成功率阈值（0.0-1.0）
    QA_SAMPLE_MIN_SUCCESS_RATE: float = float(os.getenv("QA_SAMPLE_MIN_SUCCESS_RATE", "0.7"))

    # LangGraph Checkpointer 配置
    CHECKPOINT_MODE: str = os.getenv("CHECKPOINT_MODE", "postgres")  # postgres | none
    CHECKPOINT_POSTGRES_URI: Optional[str] = os.getenv(
        "CHECKPOINT_POSTGRES_URI", 
        "postgresql://langgraph:langgraph_password_2026@localhost:5433/langgraph_checkpoints"
    )
    
    # 消息历史管理配置
    MAX_MESSAGE_HISTORY: int = int(os.getenv("MAX_MESSAGE_HISTORY", "20"))
    ENABLE_MESSAGE_SUMMARY: bool = os.getenv("ENABLE_MESSAGE_SUMMARY", "false").lower() == "true"
    SUMMARY_THRESHOLD: int = int(os.getenv("SUMMARY_THRESHOLD", "10"))
    
    # 工作流配置
    SQL_CONFIDENCE_THRESHOLD: float = float(os.getenv("SQL_CONFIDENCE_THRESHOLD", "0.7"))
    MAX_WORKFLOW_RETRIES: int = int(os.getenv("MAX_WORKFLOW_RETRIES", "3"))
    ENABLE_PARALLEL_EXECUTION: bool = os.getenv("ENABLE_PARALLEL_EXECUTION", "false").lower() == "true"

    # ==========================================
    # 快速模式配置 (Fast Mode)
    # ==========================================
    # 借鉴官方 LangGraph SQL Agent 的简洁性思想
    # 对于简单查询，跳过样本检索、图表生成等步骤，提升响应速度
    # ==========================================
    
    # 是否启用快速模式自动检测
    FAST_MODE_AUTO_DETECT: bool = os.getenv("FAST_MODE_AUTO_DETECT", "true").lower() == "true"
    
    # 快速模式查询长度阈值（字符数，短于此值可能启用快速模式）
    FAST_MODE_QUERY_LENGTH_THRESHOLD: int = int(os.getenv("FAST_MODE_QUERY_LENGTH_THRESHOLD", "50"))
    
    # 快速模式关键词（包含这些词会强制使用完整模式）
    # 如：图表、趋势、分布、比较、可视化、分析 等
    FAST_MODE_DISABLE_KEYWORDS: str = os.getenv(
        "FAST_MODE_DISABLE_KEYWORDS", 
        "图表,趋势,分布,比较,可视化,分析,chart,trend,distribution,compare,visualize,analyze"
    )
    
    # 是否在快速模式中启用 SQL Query Checker
    FAST_MODE_ENABLE_QUERY_CHECKER: bool = os.getenv("FAST_MODE_ENABLE_QUERY_CHECKER", "true").lower() == "true"
    
    # 是否在快速模式中跳过样本检索
    FAST_MODE_SKIP_SAMPLE_RETRIEVAL: bool = os.getenv("FAST_MODE_SKIP_SAMPLE_RETRIEVAL", "true").lower() == "true"
    
    # 是否在快速模式中跳过图表生成
    FAST_MODE_SKIP_CHART_GENERATION: bool = os.getenv("FAST_MODE_SKIP_CHART_GENERATION", "true").lower() == "true"

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = 'ignore'  # 忽略.env中未在Settings类中定义的额外字段

settings = Settings()
