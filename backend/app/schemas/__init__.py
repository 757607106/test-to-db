# Import and re-export schema classes
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantResponse, TenantWithStats
from app.schemas.db_connection import DBConnection, DBConnectionCreate, DBConnectionUpdate, DBConnectionInDB
from app.schemas.schema_table import SchemaTable, SchemaTableCreate, SchemaTableUpdate, SchemaTableWithRelationships
from app.schemas.schema_column import SchemaColumn, SchemaColumnCreate, SchemaColumnUpdate, SchemaColumnWithMappings
from app.schemas.schema_relationship import SchemaRelationship, SchemaRelationshipCreate, SchemaRelationshipUpdate, SchemaRelationshipDetailed
from app.schemas.value_mapping import ValueMapping, ValueMappingCreate, ValueMappingUpdate
from app.schemas.query import (
    QueryRequest, 
    QueryResponse,
    ClarificationQuestion,
    ClarificationResponse,
    AnalystInsights,
    ChatQueryRequest,
    ChatQueryResponse,
    ConversationSummary,
    ConversationDetail,
    ResumeQueryRequest,
    ResumeQueryResponse
)
from app.schemas.dashboard import (
    DashboardBase,
    DashboardCreate,
    DashboardUpdate,
    DashboardListItem,
    DashboardDetail,
    DashboardListResponse,
    LayoutUpdateRequest,
    PermissionLevel,
    PermissionBase,
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
    PermissionListResponse,
    # P1: 刷新机制
    RefreshConfig,
    GlobalRefreshRequest,
    WidgetRefreshResult,
    GlobalRefreshResponse,
)
from app.schemas.dashboard_widget import (
    WidgetBase,
    WidgetCreate,
    WidgetUpdate,
    WidgetResponse,
    WidgetRefreshResponse,
    WidgetRegenerateRequest,
    UserSimple
)
from app.schemas.llm_config import LLMConfig, LLMConfigCreate, LLMConfigUpdate
from app.schemas.agent_profile import AgentProfile, AgentProfileCreate, AgentProfileUpdate
from app.schemas.dashboard_insight import (
    TimeRangeCondition,
    InsightConditions,
    DashboardInsightRequest,
    InsightSummary,
    InsightTrend,
    InsightAnomaly,
    InsightCorrelation,
    InsightRecommendation,
    InsightResult,
    DashboardInsightResponse,
    InsightRefreshRequest,
    AdjustableTimeRange,
    AdjustableDimensionFilter,
    AdjustableAggregationLevel,
    AdjustableConditionsConfig,
    MiningRequest,
    MiningResponse,
    MiningSuggestion,
    ApplyMiningRequest,
    MiningDimension,
    # P0: 数据溯源
    ExecutionMetadata,
    SqlGenerationTrace,
    InsightLineage,
    EnhancedInsightResponse,
)
from app.schemas.agent_message import ToolResponse, SQLGenerationResult

# P2: 预测分析
from app.schemas.prediction import (
    PredictionMethod,
    PredictionRequest,
    PredictionDataPoint,
    AccuracyMetrics,
    TrendAnalysis,
    PredictionResult,
    PredictionColumnsResponse,
)

# 值域 Profile（指标库功能已废弃，仅保留 Profile）
from app.schemas.metric import (
    ColumnProfile,
    TableProfile,
)

# JOIN 规则 (已废弃 - 迁移到 Skill.join_rules)
# 保留导入以保持向后兼容，但建议使用 Skill 内嵌的 join_rules
from app.schemas.join_rule import (
    JoinRuleBase,
    JoinRuleCreate,
    JoinRuleUpdate,
    JoinRule,
    JoinRuleContext,
)

# Phase 1: 统一的 Schema 上下文格式
from app.schemas.schema_context import (
    TableInfo,
    ColumnInfo,
    RelationshipInfo,
    SchemaContext,
    normalize_schema_info,
    extract_table_names,
)

# 库存分析
from app.schemas.inventory_analysis import (
    ABCClass,
    XYZClass,
    ABCXYZRequest,
    ABCXYZResult,
    ABCXYZSummary,
    ABCXYZMatrix,
    ABCXYZDetail,
    ParetoData,
    TurnoverRequest,
    TurnoverResult,
    TurnoverDetail,
    TurnoverSummary,
    SafetyStockRequest,
    SafetyStockResult,
    SafetyStockDetail,
    SafetyStockSummary,
    SupplierEvaluationRequest,
    SupplierResult,
    SupplierDetail,
    SupplierSummary,
    InventoryAnalysisResponse,
)

