# Import and re-export schema classes
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
    ChatQueryResponse
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
    PermissionListResponse
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
    AdjustableConditionsConfig
)

