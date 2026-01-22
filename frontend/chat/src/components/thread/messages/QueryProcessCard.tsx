/**
 * 统一的查询处理卡片组件
 * 
 * 整合意图解析、SQL生成步骤、数据可视化、相似问题推荐
 * 替代原始的工具调用显示
 */
import { useState, useMemo } from "react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Database,
  Sparkles,
  BarChart2,
  Table2,
  Lightbulb,
  Clock,
  Search,
  Code2,
  Wrench,
  Play,
  MessageCircle,
  Zap,
  History,
  HardDrive,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import type { QueryContext, SQLStepEvent, ChartConfig, CacheHitEvent } from "@/types/stream-events";
import { CACHE_HIT_LABELS } from "@/types/stream-events";

interface QueryProcessCardProps {
  queryContext: QueryContext;
  onSelectQuestion?: (question: string) => void;
}

// 步骤配置
const STEP_CONFIG = {
  schema_mapping: { label: "Schema映射", icon: Database, description: "获取数据库表结构" },
  few_shot: { label: "Few-shot示例", icon: Search, description: "检索相似查询样本" },
  llm_parse: { label: "LLM解析S2SQL", icon: Sparkles, description: "使用大模型生成SQL" },
  sql_fix: { label: "修正S2SQL", icon: Wrench, description: "语法检查与修正" },
  final_sql: { label: "最终执行SQL", icon: Play, description: "执行SQL查询" },
};

const STEP_ORDER = ["schema_mapping", "few_shot", "llm_parse", "sql_fix", "final_sql"] as const;

// 图表颜色
const CHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

export function QueryProcessCard({ queryContext, onSelectQuestion }: QueryProcessCardProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(["steps"]));
  const [expandedStep, setExpandedStep] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"chart" | "table">("chart");

  const { cacheHit, intentAnalysis, sqlSteps, dataQuery, similarQuestions } = queryContext;

  // 计算总耗时
  const totalTime = useMemo(() => {
    let time = intentAnalysis?.time_ms || 0;
    time += sqlSteps.reduce((sum, step) => sum + (step.time_ms || 0), 0);
    return time;
  }, [intentAnalysis, sqlSteps]);

  // 检查是否有任何进行中的步骤
  const hasRunningStep = sqlSteps.some(s => s.status === "running");
  const hasError = sqlSteps.some(s => s.status === "error");
  const allCompleted = STEP_ORDER.every(stepKey => 
    sqlSteps.find(s => s.step === stepKey)?.status === "completed"
  );

  // 切换展开状态
  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  // 获取步骤状态图标
  const getStatusIcon = (status: string | undefined) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "running":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case "error":
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Circle className="h-4 w-4 text-slate-300" />;
    }
  };

  // 渲染图表
  const renderChart = () => {
    if (!dataQuery?.rows || dataQuery.rows.length === 0) {
      return (
        <div className="flex items-center justify-center h-[200px] text-muted-foreground">
          暂无数据
        </div>
      );
    }

    const chartConfig = dataQuery.chart_config;
    const xDataKey = chartConfig?.xDataKey || dataQuery.columns[0];
    const yDataKeys = dataQuery.columns.filter(col => col !== xDataKey).slice(0, 3);

    // 转换数据格式（确保是字典数组）
    const chartData = dataQuery.rows.map(row => {
      if (Array.isArray(row)) {
        const obj: Record<string, any> = {};
        dataQuery.columns.forEach((col, i) => {
          obj[col] = row[i];
        });
        return obj;
      }
      return row;
    });

    const ChartComponent = chartConfig?.type === "line" ? LineChart : BarChart;
    const DataComponent = chartConfig?.type === "line" ? Line : Bar;

    return (
      <ResponsiveContainer width="100%" height={250}>
        <ChartComponent data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey={xDataKey} tick={{ fontSize: 11 }} stroke="#64748b" />
          <YAxis tick={{ fontSize: 11 }} stroke="#64748b" />
          <Tooltip
            contentStyle={{
              backgroundColor: "#fff",
              border: "1px solid #e2e8f0",
              borderRadius: "6px",
              fontSize: "12px",
            }}
          />
          <Legend wrapperStyle={{ fontSize: "12px" }} />
          {yDataKeys.map((key, index) => (
            chartConfig?.type === "line" ? (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={CHART_COLORS[index % CHART_COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            ) : (
              <Bar
                key={key}
                dataKey={key}
                fill={CHART_COLORS[index % CHART_COLORS.length]}
                radius={[4, 4, 0, 0]}
              />
            )
          ))}
        </ChartComponent>
      </ResponsiveContainer>
    );
  };

  // 渲染表格
  const renderTable = () => {
    if (!dataQuery?.rows || dataQuery.rows.length === 0) {
      return (
        <div className="flex items-center justify-center h-[100px] text-muted-foreground">
          暂无数据
        </div>
      );
    }

    // 转换数据格式
    const tableData = dataQuery.rows.map(row => {
      if (Array.isArray(row)) {
        const obj: Record<string, any> = {};
        dataQuery.columns.forEach((col, i) => {
          obj[col] = row[i];
        });
        return obj;
      }
      return row;
    });

    return (
      <div className="overflow-auto max-h-[300px] border rounded-md">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800 sticky top-0">
            <tr>
              {dataQuery.columns.map((col) => (
                <th key={col} className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap border-b">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableData.slice(0, 50).map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white dark:bg-slate-900" : "bg-slate-50/50 dark:bg-slate-800/50"}>
                {dataQuery.columns.map((col) => (
                  <td key={col} className="px-3 py-2 text-slate-600 dark:text-slate-400 whitespace-nowrap border-b border-slate-100 dark:border-slate-800">
                    {formatValue(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  // 如果没有任何数据，不渲染
  if (!cacheHit && !intentAnalysis && sqlSteps.length === 0 && !dataQuery && !similarQuestions) {
    return null;
  }

  return (
    <div className="rounded-lg border bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      {/* 头部 - 总体状态 */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-50 dark:bg-slate-800 border-b">
        <div className="flex items-center gap-2">
          {hasRunningStep ? (
            <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
          ) : hasError ? (
            <XCircle className="h-5 w-5 text-red-500" />
          ) : allCompleted ? (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          ) : (
            <Circle className="h-5 w-5 text-slate-400" />
          )}
          <span className="font-medium text-slate-700 dark:text-slate-200">
            智能查询
          </span>
          {totalTime > 0 && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {totalTime}ms
            </span>
          )}
        </div>
      </div>

      {/* 缓存命中提示 */}
      {cacheHit && (
        <div className={cn(
          "flex items-center gap-2 px-4 py-2.5 border-b",
          cacheHit.hit_type === "thread_history" && "bg-purple-50 dark:bg-purple-950/30",
          cacheHit.hit_type === "exact" && "bg-green-50 dark:bg-green-950/30",
          cacheHit.hit_type === "semantic" && "bg-blue-50 dark:bg-blue-950/30"
        )}>
          {cacheHit.hit_type === "thread_history" ? (
            <History className="h-4 w-4 text-purple-500" />
          ) : cacheHit.hit_type === "exact" ? (
            <HardDrive className="h-4 w-4 text-green-500" />
          ) : (
            <Zap className="h-4 w-4 text-blue-500" />
          )}
          <span className={cn(
            "text-sm font-medium",
            cacheHit.hit_type === "thread_history" && "text-purple-700 dark:text-purple-300",
            cacheHit.hit_type === "exact" && "text-green-700 dark:text-green-300",
            cacheHit.hit_type === "semantic" && "text-blue-700 dark:text-blue-300"
          )}>
            {CACHE_HIT_LABELS[cacheHit.hit_type] || cacheHit.hit_type}
          </span>
          {cacheHit.similarity < 1 && (
            <span className="text-xs text-muted-foreground">
              (相似度: {(cacheHit.similarity * 100).toFixed(0)}%)
            </span>
          )}
          <span className="text-xs text-muted-foreground ml-auto">
            <Clock className="h-3 w-3 inline-block mr-1" />
            {cacheHit.time_ms}ms
          </span>
        </div>
      )}

      {/* 意图解析 */}
      {intentAnalysis && (
        <div className="border-b">
          <button
            onClick={() => toggleSection("intent")}
            className="flex items-center gap-2 w-full px-4 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
          >
            <CheckCircle2 className="h-4 w-4 text-green-500" />
            <span className="font-medium text-sm">意图解析</span>
            <span className="text-xs text-muted-foreground">({intentAnalysis.time_ms}ms)</span>
            {expandedSections.has("intent") ? (
              <ChevronDown className="h-4 w-4 ml-auto text-slate-400" />
            ) : (
              <ChevronRight className="h-4 w-4 ml-auto text-slate-400" />
            )}
          </button>
          {expandedSections.has("intent") && (
            <div className="px-4 pb-3 grid grid-cols-3 gap-3 text-sm">
              <div>
                <span className="text-muted-foreground text-xs">数据集</span>
                <div className="text-blue-600 font-medium">{intentAnalysis.dataset}</div>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">查询模式</span>
                <div className="text-blue-600 font-medium">{intentAnalysis.query_mode}</div>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">指标</span>
                <div className="text-blue-600 font-medium">{intentAnalysis.metrics.join(", ") || "默认"}</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* SQL 生成步骤 */}
      {sqlSteps.length > 0 && (
        <div className="border-b">
          <button
            onClick={() => toggleSection("steps")}
            className="flex items-center gap-2 w-full px-4 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
          >
            {hasRunningStep ? (
              <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
            ) : hasError ? (
              <XCircle className="h-4 w-4 text-red-500" />
            ) : (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            )}
            <span className="font-medium text-sm">SQL 生成</span>
            <span className="text-xs text-muted-foreground">
              ({sqlSteps.reduce((sum, s) => sum + (s.time_ms || 0), 0)}ms)
            </span>
            {expandedSections.has("steps") ? (
              <ChevronDown className="h-4 w-4 ml-auto text-slate-400" />
            ) : (
              <ChevronRight className="h-4 w-4 ml-auto text-slate-400" />
            )}
          </button>
          {expandedSections.has("steps") && (
            <div className="px-4 pb-3">
              {/* 步骤按钮组 */}
              <div className="flex flex-wrap gap-2 mb-2">
                {STEP_ORDER.map((stepKey) => {
                  const step = sqlSteps.find(s => s.step === stepKey);
                  const config = STEP_CONFIG[stepKey];
                  const Icon = config.icon;
                  const isExpanded = expandedStep === stepKey;

                  return (
                    <button
                      key={stepKey}
                      onClick={() => setExpandedStep(isExpanded ? null : stepKey)}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs border transition-all",
                        step?.status === "completed" && "bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300",
                        step?.status === "running" && "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 animate-pulse",
                        step?.status === "error" && "bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300",
                        !step?.status && "bg-slate-50 text-slate-500 border-slate-200 dark:bg-slate-800 dark:text-slate-400"
                      )}
                    >
                      {getStatusIcon(step?.status)}
                      <Icon className="h-3 w-3" />
                      <span>{config.label}</span>
                      {step?.result && (
                        isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />
                      )}
                    </button>
                  );
                })}
              </div>

              {/* 展开的步骤详情 */}
              {expandedStep && (
                <div className="mt-2 bg-slate-50 dark:bg-slate-800 rounded-md p-3">
                  {sqlSteps.filter(s => s.step === expandedStep).map((step, idx) => (
                    <div key={idx}>
                      <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
                        <span>{STEP_CONFIG[step.step as keyof typeof STEP_CONFIG]?.description}</span>
                        {step.time_ms > 0 && <span>• {step.time_ms}ms</span>}
                      </div>
                      {step.result && (
                        <pre className="text-xs text-slate-600 dark:text-slate-300 whitespace-pre-wrap break-all font-mono bg-white dark:bg-slate-900 p-2 rounded border">
                          {step.result}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 数据查询结果 */}
      {dataQuery && (
        <div className="border-b">
          <div className="flex items-center justify-between px-4 py-2">
            <button
              onClick={() => toggleSection("data")}
              className="flex items-center gap-2 text-left"
            >
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <span className="font-medium text-sm">数据查询</span>
              <span className="text-xs text-muted-foreground">
                ({dataQuery.row_count || dataQuery.rows?.length || 0} 条)
              </span>
              {expandedSections.has("data") ? (
                <ChevronDown className="h-4 w-4 text-slate-400" />
              ) : (
                <ChevronRight className="h-4 w-4 text-slate-400" />
              )}
            </button>
            {expandedSections.has("data") && (
              <div className="flex items-center gap-2">
                <BarChart2 className={cn("h-4 w-4", viewMode === "chart" ? "text-blue-500" : "text-slate-400")} />
                <Switch
                  checked={viewMode === "table"}
                  onCheckedChange={(v) => setViewMode(v ? "table" : "chart")}
                />
                <Table2 className={cn("h-4 w-4", viewMode === "table" ? "text-blue-500" : "text-slate-400")} />
              </div>
            )}
          </div>
          {expandedSections.has("data") && (
            <div className="px-4 pb-3">
              {viewMode === "chart" ? renderChart() : renderTable()}
            </div>
          )}
        </div>
      )}

      {/* 相似问题推荐 */}
      {similarQuestions && similarQuestions.questions.length > 0 && (
        <div>
          <button
            onClick={() => toggleSection("similar")}
            className="flex items-center gap-2 w-full px-4 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
          >
            <Lightbulb className="h-4 w-4 text-amber-500" />
            <span className="font-medium text-sm">推荐问题</span>
            <span className="text-xs text-muted-foreground">({similarQuestions.questions.length})</span>
            {expandedSections.has("similar") ? (
              <ChevronDown className="h-4 w-4 ml-auto text-slate-400" />
            ) : (
              <ChevronRight className="h-4 w-4 ml-auto text-slate-400" />
            )}
          </button>
          {expandedSections.has("similar") && (
            <div className="px-4 pb-3 space-y-1">
              {similarQuestions.questions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => onSelectQuestion?.(q)}
                  className="flex items-start gap-2 w-full text-left p-2 rounded-md text-sm text-slate-600 dark:text-slate-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 hover:text-blue-600"
                >
                  <MessageCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{q}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// 格式化单元格值
function formatValue(value: any): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") {
    return value.toLocaleString("zh-CN", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }
  return String(value);
}
