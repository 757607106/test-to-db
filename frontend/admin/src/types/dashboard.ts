// Dashboard相关类型定义

export interface UserSimple {
  id: number;
  username: string;
  display_name?: string;
  avatar_url?: string;
}

// ===== P1: 动态刷新类型定义 =====

export interface RefreshConfig {
  enabled: boolean;
  intervalSeconds: number;
  autoRefreshWidgetIds: number[];
  lastGlobalRefresh?: string;
}

export interface GlobalRefreshRequest {
  force: boolean;
  widgetIds?: number[];
}

export interface WidgetRefreshResult {
  widgetId: number;
  success: boolean;
  durationMs: number;
  error?: string;
  fromCache: boolean;
  rowCount: number;
}

export interface GlobalRefreshResponse {
  successCount: number;
  failedCount: number;
  results: Record<number, WidgetRefreshResult>;
  totalDurationMs: number;
  refreshTimestamp: string;
}

// ===== Dashboard 基础类型 =====

export interface Dashboard {
  id: number;
  name: string;
  description?: string;
  owner_id: number;
  owner?: UserSimple;
  is_public: boolean;
  tags?: string[];
  layout_config: any[];
  created_at: string;
  updated_at: string;
  deleted_at?: string;
}

export interface DashboardListItem {
  id: number;
  name: string;
  description?: string;
  owner_id: number;
  owner?: UserSimple;
  widget_count: number;
  permission_level?: string;
  is_public: boolean;
  tags?: string[];
  created_at: string;
  updated_at: string;
}

export interface DashboardDetail extends Dashboard {
  widgets: Widget[];
  permissions: DashboardPermission[];
  permission_level?: string;
}

export interface DashboardCreate {
  name: string;
  description?: string;
  is_public?: boolean;
  tags?: string[];
}

export interface DashboardUpdate {
  name?: string;
  description?: string;
  is_public?: boolean;
  tags?: string[];
}

export interface DashboardListResponse {
  total: number;
  page: number;
  page_size: number;
  items: DashboardListItem[];
}

export interface Widget {
  id: number;
  dashboard_id: number;
  widget_type: 'chart' | 'table' | 'text' | 'insight_analysis' | 'inventory_analysis';
  title: string;
  connection_id: number;
  query_config: WidgetQueryConfig;
  chart_config?: any;
  position_config: WidgetPositionConfig;
  refresh_interval: number;
  last_refresh_at?: string;
  data_cache?: any;
  created_at: string;
  updated_at: string;
  connection_name?: string;
}

export interface WidgetQueryConfig {
  original_query: string;
  generated_sql: string;
  parameters?: Record<string, any>;
  editable_params?: string[];
  conversation_id?: string;
  edit_history?: Array<{
    timestamp: string;
    previous_query: string;
    new_query: string;
  }>;
}

export interface WidgetPositionConfig {
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
}

export interface WidgetCreate {
  widget_type: 'chart' | 'table' | 'text' | 'insight_analysis' | 'inventory_analysis';
  title: string;
  connection_id: number;
  query_config: WidgetQueryConfig;
  chart_config?: any;
  position_config: WidgetPositionConfig;
  refresh_interval?: number;
}

export interface WidgetUpdate {
  title?: string;
  chart_config?: ChartConfig;
  refresh_interval?: number;
  position_config?: WidgetPositionConfig;
}

// 图表配置类型
export interface ChartConfig {
  chart_type: string;
  title?: string;
  color_scheme?: string;
  custom_colors?: string[];
  legend?: {
    show: boolean;
    position: 'top' | 'bottom' | 'left' | 'right';
  };
  axis?: {
    xAxisName?: string;
    yAxisName?: string;
    showGrid?: boolean;
  };
  tooltip?: {
    show: boolean;
    trigger: 'item' | 'axis';
  };
  series_config?: {
    smooth?: boolean;
    stack?: boolean;
    label?: boolean;
    radius?: [string, string];
  };
  data_mapping?: {
    x_column?: string;
    y_columns?: string[];
    category_column?: string;
  };
}

// AI 图表推荐请求
export interface AIChartRecommendRequest {
  widget_id: number;
  data_sample?: any;
  intent?: string;
}

// AI 图表推荐响应
export interface AIChartRecommendResponse {
  recommended_type: string;
  confidence: number;
  reasoning: string;
  chart_config: ChartConfig;
  alternatives?: Array<{
    type: string;
    confidence: number;
    description: string;
  }>;
}

export interface WidgetRefreshResponse {
  id: number;
  data_cache?: any;
  last_refresh_at: string;
  refresh_duration_ms: number;
}

export interface WidgetRegenerateRequest {
  mode: 'params' | 'full';
  updated_query?: string;
  parameters?: Record<string, any>;
}

export interface WidgetRegenerateResponse {
  id: number;
  query_config: WidgetQueryConfig;
  data_cache?: any;
  last_refresh_at: string;
  message: string;
}

export interface DashboardPermission {
  id: number;
  dashboard_id: number;
  user_id: number;
  user?: UserSimple;
  permission_level: 'owner' | 'editor' | 'viewer';
  granted_by: number;
  created_at: string;
}

export interface PermissionCreate {
  user_id: number;
  permission_level: 'owner' | 'editor' | 'viewer';
}

export interface PermissionUpdate {
  permission_level: 'owner' | 'editor' | 'viewer';
}

export interface LayoutUpdateRequest {
  layout: Array<{
    widget_id: number;
    x: number;
    y: number;
    w: number;
    h: number;
  }>;
}

// Insight相关类型定义
export interface InsightSummary {
  description?: string;
  data_points?: number;
  key_metrics?: Record<string, any>;
}

export interface InsightTrend {
  description?: string;
  direction?: 'up' | 'down' | 'stable';
  change_rate?: number;
}

export interface InsightAnomaly {
  metric?: string;
  description: string;
  severity?: 'high' | 'medium' | 'low';
}

export interface InsightCorrelation {
  entities?: string[];
  description: string;
  strength?: number;
}

export interface InsightRecommendation {
  category?: string;
  content: string;
  priority?: 'high' | 'medium' | 'low';
}
