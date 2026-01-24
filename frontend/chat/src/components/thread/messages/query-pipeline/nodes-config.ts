/**
 * 查询流水线节点配置
 * 
 * 与后端 Hub-and-Spoke 架构对齐
 */
import {
  Database,
  Sparkles,
  Play,
  Brain,
  MessageCircle,
  BarChart3,
  Circle,
  Loader2,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import type { QueryContext } from "@/types/stream-events";

// 执行节点配置接口
export interface NodeConfig {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  dataKey: keyof QueryContext | "sql_step";
  stepKey?: string;      // 对应后端的 step 名称
  stepKeys?: string[];   // 兼容多个后端 step 名称
  toolName?: string;     // 对应的工具名称（用于显示）
}

/**
 * Hub-and-Spoke 架构节点配置
 * 
 * 映射关系:
 * - schema_agent / schema_mapping → Schema 分析
 * - clarification → 需求澄清
 * - sql_generator / llm_parse / sql_fix → SQL 生成
 * - sql_executor / final_sql → SQL 执行
 * - data_analyst / data_analysis → 数据分析
 * - chart_generator / chart_generation → 图表生成
 */
export const PIPELINE_NODES: NodeConfig[] = [
  {
    key: "intent",
    label: "意图解析",
    icon: Brain,
    description: "理解用户查询意图，识别数据集和查询模式",
    dataKey: "intentAnalysis",
    toolName: "analyze_user_query",
  },
  {
    key: "schema_agent",
    label: "Schema 分析",
    icon: Database,
    description: "获取相关表结构和字段信息",
    dataKey: "sql_step",
    stepKey: "schema_agent",
    stepKeys: ["schema_agent", "schema_mapping"],
    toolName: "retrieve_database_schema",
  },
  {
    key: "clarification",
    label: "需求澄清",
    icon: MessageCircle,
    description: "澄清模糊查询，确认用户意图",
    dataKey: "sql_step",
    stepKey: "clarification",
    toolName: "clarify_user_intent",
  },
  {
    key: "sql_generator",
    label: "SQL 生成",
    icon: Sparkles,
    description: "使用大语言模型生成 SQL 查询",
    dataKey: "sql_step",
    stepKey: "sql_generator",
    stepKeys: ["sql_generator", "llm_parse", "sql_fix", "few_shot"],
    toolName: "generate_sql_query",
  },
  {
    key: "sql_executor",
    label: "SQL 执行",
    icon: Play,
    description: "执行 SQL 查询，获取数据",
    dataKey: "sql_step",
    stepKey: "sql_executor",
    stepKeys: ["sql_executor", "final_sql"],
    toolName: "execute_sql_query",
  },
  {
    key: "data_analyst",
    label: "数据分析",
    icon: Sparkles,
    description: "分析查询结果，生成洞察与解释",
    dataKey: "sql_step",
    stepKey: "data_analyst",
    stepKeys: ["data_analyst", "data_analysis"],
    toolName: "analyze_query_results",
  },
  {
    key: "chart_generator",
    label: "图表生成",
    icon: BarChart3,
    description: "生成可视化图表配置",
    dataKey: "sql_step",
    stepKey: "chart_generator",
    stepKeys: ["chart_generator", "chart_generation"],
    toolName: "generate_chart",
  },
];

// 节点状态类型
export type NodeStatus = "pending" | "running" | "completed" | "error" | "skipped";

// 状态样式配置
export const STATUS_CONFIG: Record<NodeStatus, {
  bg: string;
  border: string;
  text: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
  animate?: boolean;
}> = {
  pending: {
    bg: "bg-slate-100",
    border: "border-slate-200",
    text: "text-slate-400",
    icon: Circle,
    iconColor: "text-slate-300",
    animate: false,
  },
  running: {
    bg: "bg-blue-50",
    border: "border-blue-200",
    text: "text-blue-600",
    icon: Loader2,
    iconColor: "text-blue-500",
    animate: true,
  },
  completed: {
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    text: "text-emerald-600",
    icon: CheckCircle2,
    iconColor: "text-emerald-500",
    animate: false,
  },
  error: {
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-600",
    icon: XCircle,
    iconColor: "text-red-500",
    animate: false,
  },
  skipped: {
    bg: "bg-slate-50",
    border: "border-slate-200",
    text: "text-slate-400",
    icon: Circle,
    iconColor: "text-slate-300",
    animate: false,
  },
};

// 缓存命中样式配置
export const CACHE_HIT_CONFIG = {
  thread_history: { icon: "History", color: "purple", bg: "from-purple-50 to-purple-100/50" },
  exact: { icon: "HardDrive", color: "emerald", bg: "from-emerald-50 to-emerald-100/50" },
  semantic: { icon: "Zap", color: "blue", bg: "from-blue-50 to-blue-100/50" },
};

/**
 * 根据后端返回的 step 名称查找对应的节点配置
 */
export function findNodeByStep(step: string): NodeConfig | undefined {
  return PIPELINE_NODES.find(node => 
    node.stepKey === step || node.stepKeys?.includes(step)
  );
}

/**
 * 检查是否为完成状态的步骤
 */
export function isCompletedStep(step: string): boolean {
  const completionSteps = [
    "final_sql", "sql_executor",
    "data_analysis", "data_analyst",
    "chart_generation", "chart_generator"
  ];
  return completionSteps.includes(step);
}
