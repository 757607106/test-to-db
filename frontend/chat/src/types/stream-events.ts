/**
 * 流式事件类型定义
 * 
 * 与后端 backend/app/schemas/stream_events.py 保持一致
 * 用于处理 LangGraph custom streaming mode 的事件数据
 */

/**
 * 缓存命中事件 - 展示缓存命中信息
 * 
 * hit_type 类型:
 * - thread_history: 同一对话内历史命中
 * - exact: 全局缓存精确匹配
 * - semantic: 全局缓存语义匹配 (>=95%)
 */
export interface CacheHitEvent {
  type: "cache_hit";
  hit_type: "thread_history" | "exact" | "semantic";
  similarity: number;          // 相似度 (0-1)
  original_query?: string;     // 原始匹配的查询
  time_ms: number;             // 耗时(毫秒)
}

/**
 * 意图解析事件 - 展示用户查询的解析结果
 */
export interface IntentAnalysisEvent {
  type: "intent_analysis";
  dataset: string;       // 数据集名称
  query_mode: string;    // 查询模式: 聚合模式/明细模式
  metrics: string[];     // 指标列表
  filters: {
    date_range?: [string, string];  // 日期范围
    [key: string]: any;
  };
  time_ms: number;       // 耗时(毫秒)
}

/**
 * SQL生成步骤事件 - 展示SQL生成的各个步骤
 * 
 * 与后端 Hub-and-Spoke 架构节点对齐:
 * - schema_agent: Schema 分析
 * - clarification: 需求澄清 (支持 interrupt)
 * - sql_generator: SQL 生成
 * - sql_executor: SQL 执行
 * - data_analyst: 数据分析
 * - chart_generator: 图表生成
 * - error_recovery: 错误恢复
 * - general_chat: 闲聊处理
 * 
 * 兼容旧版节点名称:
 * - schema_mapping, few_shot, llm_parse, sql_fix, final_sql, data_analysis, chart_generation
 */
export interface SQLStepEvent {
  type: "sql_step";
  step: 
    // P2: 智能规划节点
    | "intent_analysis"
    | "query_planning"
    // P2.1: 多步执行节点
    | "result_aggregator"
    // 新版 Hub-and-Spoke 节点
    | "schema_agent"
    | "clarification"
    | "sql_generator"
    | "sql_executor"
    | "data_analyst"
    | "chart_generator"
    | "error_recovery"
    | "general_chat"
    // 兼容旧版节点名称
    | "schema_mapping"
    | "few_shot"
    | "llm_parse"
    | "sql_fix"
    | "final_sql"
    | "data_analysis"
    | "chart_generation";
  status: "pending" | "running" | "completed" | "error" | "skipped";
  result?: string;       // 步骤结果
  time_ms: number;       // 耗时(毫秒)
}

/**
 * 图表配置
 */
export interface ChartConfig {
  type: "line" | "bar" | "pie" | "area";
  xAxis: string;
  yAxis: string;
  dataKey: string;
  xDataKey: string;
}

/**
 * 数据查询事件 - 展示查询结果数据
 */
export interface DataQueryEvent {
  type: "data_query";
  columns: string[];                    // 列名列表
  rows: Record<string, any>[];          // 数据行
  row_count: number;                    // 总行数
  chart_config?: ChartConfig;           // Recharts 图表配置
  title?: string;                       // 数据标题
}

/**
 * 相似问题事件 - 展示推荐的相似问题
 */
export interface SimilarQuestionsEvent {
  type: "similar_questions";
  questions: string[];                  // 相似问题列表
}

/**
 * 洞察项类型
 */
export interface InsightItem {
  type: "trend" | "anomaly" | "metric" | "comparison";
  description: string;
}

/**
 * 数据洞察事件 - 展示 AI 分析的业务洞察
 * 
 * 包含:
 * - summary: 一句话摘要
 * - insights: 结构化洞察列表 (趋势/异常/指标/对比)
 * - recommendations: 业务建议列表
 */
export interface InsightEvent {
  type: "insight";
  summary: string;                      // 一句话摘要
  insights: InsightItem[];              // 结构化洞察列表
  recommendations: string[];            // 业务建议列表
  raw_content?: string;                 // 原始 Markdown 内容
  time_ms: number;                      // 分析耗时(毫秒)
}

/**
 * 节点状态事件 - 展示 Agent 节点的执行状态
 * 
 * 用于向前端通知节点执行状态，特别是错误恢复等场景
 */
export interface NodeStatusEvent {
  type: "node_status";
  node: string;                         // 节点名称
  status: "running" | "completed" | "error" | "retrying";
  message?: string;                     // 用户友好的状态消息
  metadata?: {
    retry_count?: number;
    max_retries?: number;
    error_type?: string;
    next_stage?: string;
    [key: string]: any;
  };
}

/**
 * 所有流式事件的联合类型
 */
export type StreamEvent = 
  | CacheHitEvent
  | IntentAnalysisEvent 
  | SQLStepEvent 
  | DataQueryEvent 
  | SimilarQuestionsEvent
  | InsightEvent
  | NodeStatusEvent;

/**
 * 查询上下文 - 聚合所有流式事件数据
 */
export interface QueryContext {
  cacheHit?: CacheHitEvent;               // 缓存命中信息
  intentAnalysis?: IntentAnalysisEvent;
  sqlSteps: SQLStepEvent[];
  dataQuery?: DataQueryEvent;
  similarQuestions?: SimilarQuestionsEvent;
  insight?: InsightEvent;                 // 数据洞察
  nodeStatus?: NodeStatusEvent;           // 节点状态（用于错误恢复等）
}

/**
 * 创建空的查询上下文
 */
export function createEmptyQueryContext(): QueryContext {
  return {
    sqlSteps: []
  };
}

/**
 * 检查是否为流式事件
 */
export function isStreamEvent(event: unknown): event is StreamEvent {
  if (typeof event !== "object" || event === null) return false;
  const e = event as Record<string, unknown>;
  return (
    e.type === "cache_hit" ||
    e.type === "intent_analysis" ||
    e.type === "sql_step" ||
    e.type === "data_query" ||
    e.type === "similar_questions" ||
    e.type === "insight" ||
    e.type === "node_status"
  );
}

/**
 * 缓存命中类型标签映射
 */
export const CACHE_HIT_LABELS: Record<string, string> = {
  thread_history: "对话历史命中",
  exact: "精确缓存命中",
  semantic: "语义缓存命中"
};

/**
 * SQL步骤标签映射 - 包含新旧节点名称
 */
export const SQL_STEP_LABELS: Record<string, string> = {
  // P2: 智能规划节点
  intent_analysis: "意图分析",
  query_planning: "查询规划",
  // P2.1: 多步执行节点
  result_aggregator: "结果聚合",
  // 新版 Hub-and-Spoke 节点
  schema_agent: "Schema 分析",
  clarification: "需求澄清",
  sql_generator: "SQL 生成",
  sql_executor: "SQL 执行",
  data_analyst: "数据分析",
  chart_generator: "图表生成",
  error_recovery: "错误恢复",
  general_chat: "闲聊处理",
  // 兼容旧版节点名称
  schema_mapping: "Schema映射",
  few_shot: "Few-shot示例",
  llm_parse: "LLM解析S2SQL",
  sql_fix: "修正S2SQL",
  final_sql: "执行SQL查询",
  data_analysis: "数据分析",
  chart_generation: "图表生成"
};
