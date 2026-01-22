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
 */
export interface SQLStepEvent {
  type: "sql_step";
  step: "schema_mapping" | "few_shot" | "llm_parse" | "sql_fix" | "final_sql" | "data_analysis" | "chart_generation";
  status: "pending" | "running" | "completed" | "error";
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
 * 所有流式事件的联合类型
 */
export type StreamEvent = 
  | CacheHitEvent
  | IntentAnalysisEvent 
  | SQLStepEvent 
  | DataQueryEvent 
  | SimilarQuestionsEvent;

/**
 * 查询上下文 - 聚合所有流式事件数据
 */
export interface QueryContext {
  cacheHit?: CacheHitEvent;               // 缓存命中信息
  intentAnalysis?: IntentAnalysisEvent;
  sqlSteps: SQLStepEvent[];
  dataQuery?: DataQueryEvent;
  similarQuestions?: SimilarQuestionsEvent;
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
    e.type === "similar_questions"
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
 * SQL步骤标签映射
 */
export const SQL_STEP_LABELS: Record<string, string> = {
  schema_mapping: "Schema映射",
  few_shot: "Few-shot示例",
  llm_parse: "LLM解析S2SQL",
  sql_fix: "修正S2SQL",
  final_sql: "执行SQL查询",
  data_analysis: "数据分析",
  chart_generation: "图表生成"
};
