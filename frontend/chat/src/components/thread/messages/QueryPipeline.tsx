/**
 * 统一查询流程管线组件
 * 
 * 整合所有工具调用，展示完整的执行流程
 * 支持点击展开查看详细数据
 */
import { useState, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Database,
  Sparkles,
  Search,
  Wrench,
  Play,
  Brain,
  Clock,
  Copy,
  Check,
  BarChart2,
  Table2,
  Lightbulb,
  MessageCircle,
  History,
  Zap,
  HardDrive,
  ArrowDown,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import type { QueryContext, SQLStepEvent } from "@/types/stream-events";
import { CACHE_HIT_LABELS } from "@/types/stream-events";
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

// 图表颜色配置
const CHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

// 执行节点配置
interface NodeConfig {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  dataKey: keyof QueryContext | "sql_step";
  stepKey?: string;
}

const PIPELINE_NODES: NodeConfig[] = [
  {
    key: "intent",
    label: "意图解析",
    icon: Brain,
    description: "理解用户查询意图，识别数据集和查询模式",
    dataKey: "intentAnalysis",
  },
  {
    key: "schema_mapping",
    label: "Schema映射",
    icon: Database,
    description: "获取相关表结构和字段信息",
    dataKey: "sql_step",
    stepKey: "schema_mapping",
  },
  {
    key: "few_shot",
    label: "Few-shot示例",
    icon: Search,
    description: "检索相似查询示例作为参考",
    dataKey: "sql_step",
    stepKey: "few_shot",
  },
  {
    key: "llm_parse",
    label: "LLM解析S2SQL",
    icon: Sparkles,
    description: "使用大语言模型生成SQL查询",
    dataKey: "sql_step",
    stepKey: "llm_parse",
  },
  {
    key: "sql_fix",
    label: "修正S2SQL",
    icon: Wrench,
    description: "语法检查与SQL优化修正",
    dataKey: "sql_step",
    stepKey: "sql_fix",
  },
  {
    key: "final_sql",
    label: "最终执行SQL",
    icon: Play,
    description: "执行最终SQL查询",
    dataKey: "sql_step",
    stepKey: "final_sql",
  },
];

interface QueryPipelineProps {
  queryContext: QueryContext;
  onSelectQuestion?: (question: string) => void;
}

type NodeStatus = "pending" | "running" | "completed" | "error" | "skipped";

export function QueryPipeline({ queryContext, onSelectQuestion }: QueryPipelineProps) {
  // 默认展开，但允许用户折叠
  const [isContainerExpanded, setIsContainerExpanded] = useState(true);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [copiedSql, setCopiedSql] = useState(false);
  const [viewMode, setViewMode] = useState<"chart" | "table">("table");

  const { cacheHit, intentAnalysis, sqlSteps, dataQuery, similarQuestions } = queryContext;

  // 获取节点状态
  const getNodeStatus = (node: NodeConfig): NodeStatus => {
    if (node.dataKey === "intentAnalysis") {
      return intentAnalysis ? "completed" : "pending";
    }
    
    if (node.dataKey === "sql_step" && node.stepKey) {
      const step = sqlSteps.find(s => s.step === node.stepKey);
      if (!step) return "pending";
      return step.status as NodeStatus;
    }
    
    return "pending";
  };

  // 获取节点数据
  const getNodeData = (node: NodeConfig): any => {
    if (node.dataKey === "intentAnalysis") {
      return intentAnalysis;
    }
    
    if (node.dataKey === "sql_step" && node.stepKey) {
      return sqlSteps.find(s => s.step === node.stepKey);
    }
    
    return null;
  };

  // 计算总耗时
  const totalTime = useMemo(() => {
    let time = intentAnalysis?.time_ms || 0;
    time += sqlSteps.reduce((sum, step) => sum + (step.time_ms || 0), 0);
    return time;
  }, [intentAnalysis, sqlSteps]);

  // 检查整体状态
  const hasRunningStep = sqlSteps.some(s => s.status === "running");
  const hasError = sqlSteps.some(s => s.status === "error");
  const isCompleted = sqlSteps.some(s => s.step === "final_sql" && s.status === "completed");

  // 切换节点展开状态
  const toggleNode = (key: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // 复制SQL
  const copySQL = (sql: string) => {
    navigator.clipboard.writeText(sql);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  // 如果没有数据，不渲染
  if (!cacheHit && !intentAnalysis && sqlSteps.length === 0 && !dataQuery) {
    return null;
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-gradient-to-b from-white to-slate-50/50 shadow-sm overflow-hidden transition-all duration-300">
      {/* 头部 - 总体状态 (可点击折叠) */}
      <button 
        onClick={() => setIsContainerExpanded(!isContainerExpanded)}
        className="w-full flex items-center justify-between px-5 py-4 bg-gradient-to-r from-slate-50 to-white border-b border-slate-100 hover:bg-slate-50/80 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            "flex items-center justify-center w-10 h-10 rounded-xl transition-colors duration-300",
            hasError ? "bg-red-100" : hasRunningStep ? "bg-blue-100" : isCompleted ? "bg-emerald-100" : "bg-slate-100"
          )}>
            {hasRunningStep ? (
              <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
            ) : hasError ? (
              <XCircle className="h-5 w-5 text-red-600" />
            ) : isCompleted ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            ) : (
              <Circle className="h-5 w-5 text-slate-400" />
            )}
          </div>
          <div className="text-left">
            <h3 className="font-semibold text-slate-800">智能查询</h3>
            <p className="text-xs text-slate-500 flex items-center gap-2">
              {hasRunningStep ? "正在处理中..." : hasError ? "执行出错" : isCompleted ? "查询完成" : "等待执行"}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {totalTime > 0 && (
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 rounded-lg">
              <Clock className="h-3.5 w-3.5 text-slate-500" />
              <span className="text-sm font-medium text-slate-600">{totalTime}ms</span>
            </div>
          )}
          <motion.div
            animate={{ rotate: isContainerExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronDown className="h-5 w-5 text-slate-400" />
          </motion.div>
        </div>
      </button>

      {/* 缓存命中提示 - 即使折叠也显示，除非完全没命中 */}
      {cacheHit && isContainerExpanded && (
        <CacheHitBanner cacheHit={cacheHit} />
      )}

      {/* 执行流水线内容区域 */}
      <AnimatePresence>
        {isContainerExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="p-5">
              <div className="space-y-0">
                {PIPELINE_NODES.map((node, index) => {
                  const status = getNodeStatus(node);
                  const nodeData = getNodeData(node);
                  const isExpanded = expandedNodes.has(node.key);
                  const isLast = index === PIPELINE_NODES.length - 1;

                  return (
                    <div key={node.key} className="relative">
                      {/* 连接线 */}
                      {!isLast && (
                        <div className="absolute left-5 top-12 w-0.5 h-6 bg-gradient-to-b from-slate-200 to-slate-100" />
                      )}
                      
                      {/* 节点卡片 */}
                      <PipelineNode
                        node={node}
                        status={status}
                        data={nodeData}
                        isExpanded={isExpanded}
                        onToggle={() => toggleNode(node.key)}
                        copySQL={copySQL}
                        copiedSql={copiedSql}
                      />
                    </div>
                  );
                })}
              </div>

              {/* SQL执行结果 */}
              {dataQuery && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 }}
                >
                  <DataQueryResult
                    dataQuery={dataQuery}
                    viewMode={viewMode}
                    onViewModeChange={setViewMode}
                  />
                </motion.div>
              )}

              {/* 相似问题推荐 */}
              {similarQuestions && similarQuestions.questions.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                >
                  <SimilarQuestionsSection
                    questions={similarQuestions.questions}
                    onSelect={onSelectQuestion}
                  />
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// 缓存命中横幅
function CacheHitBanner({ cacheHit }: { cacheHit: QueryContext["cacheHit"] }) {
  if (!cacheHit) return null;

  const config = {
    thread_history: { icon: History, color: "purple", bg: "from-purple-50 to-purple-100/50" },
    exact: { icon: HardDrive, color: "emerald", bg: "from-emerald-50 to-emerald-100/50" },
    semantic: { icon: Zap, color: "blue", bg: "from-blue-50 to-blue-100/50" },
  };

  const c = config[cacheHit.hit_type] || config.semantic;
  const Icon = c.icon;

  return (
    <div className={cn("flex items-center gap-3 px-5 py-3 bg-gradient-to-r border-b", c.bg)}>
      <div className={cn("p-1.5 rounded-lg", `bg-${c.color}-100`)}>
        <Icon className={cn("h-4 w-4", `text-${c.color}-600`)} />
      </div>
      <div className="flex-1">
        <span className={cn("text-sm font-medium", `text-${c.color}-700`)}>
          {CACHE_HIT_LABELS[cacheHit.hit_type]}
        </span>
        {cacheHit.similarity < 1 && (
          <span className="text-xs text-slate-500 ml-2">
            相似度: {(cacheHit.similarity * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <span className="text-xs text-slate-500 flex items-center gap-1">
        <Clock className="h-3 w-3" />
        {cacheHit.time_ms}ms
      </span>
    </div>
  );
}

// 流水线节点组件
interface PipelineNodeProps {
  node: NodeConfig;
  status: NodeStatus;
  data: any;
  isExpanded: boolean;
  onToggle: () => void;
  copySQL: (sql: string) => void;
  copiedSql: boolean;
}

function PipelineNode({ node, status, data, isExpanded, onToggle, copySQL, copiedSql }: PipelineNodeProps) {
  const Icon = node.icon;
  const hasData = data && (
    (node.key === "intent" && data) ||
    (data.result || data.time_ms > 0)
  );

  const statusConfig: Record<NodeStatus, { bg: string; border: string; text: string; icon: React.ComponentType<{ className?: string }>; iconColor: string; animate?: boolean }> = {
    pending: { bg: "bg-slate-100", border: "border-slate-200", text: "text-slate-400", icon: Circle, iconColor: "text-slate-300", animate: false },
    running: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-600", icon: Loader2, iconColor: "text-blue-500", animate: true },
    completed: { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-600", icon: CheckCircle2, iconColor: "text-emerald-500", animate: false },
    error: { bg: "bg-red-50", border: "border-red-200", text: "text-red-600", icon: XCircle, iconColor: "text-red-500", animate: false },
    skipped: { bg: "bg-slate-50", border: "border-slate-200", text: "text-slate-400", icon: Circle, iconColor: "text-slate-300", animate: false },
  };

  const config = statusConfig[status];
  const StatusIcon = config.icon;

  return (
    <div className="mb-3">
      <motion.button
        onClick={onToggle}
        disabled={!hasData}
        className={cn(
          "w-full flex items-center gap-3 p-3 rounded-xl border transition-all",
          config.bg, config.border,
          hasData && "hover:shadow-md cursor-pointer",
          !hasData && "cursor-default opacity-75",
          config.animate && "animate-pulse"
        )}
        whileHover={hasData ? { scale: 1.01 } : {}}
        whileTap={hasData ? { scale: 0.99 } : {}}
      >
        {/* 状态图标 */}
        <div className={cn(
          "flex items-center justify-center w-10 h-10 rounded-lg",
          status === "completed" ? "bg-emerald-100" :
          status === "running" ? "bg-blue-100" :
          status === "error" ? "bg-red-100" : "bg-slate-100"
        )}>
          <StatusIcon className={cn(
            "h-5 w-5",
            config.iconColor,
            config.animate && "animate-spin"
          )} />
        </div>

        {/* 节点信息 */}
        <div className="flex-1 text-left">
          <div className="flex items-center gap-2">
            <Icon className={cn("h-4 w-4", config.text)} />
            <span className={cn("font-medium text-sm", config.text)}>{node.label}</span>
            {data?.time_ms > 0 && (
              <span className="text-xs text-slate-400 ml-auto mr-2">{data.time_ms}ms</span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">{node.description}</p>
        </div>

        {/* 展开箭头 */}
        {hasData && (
          <motion.div
            animate={{ rotate: isExpanded ? 90 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronRight className="h-4 w-4 text-slate-400" />
          </motion.div>
        )}
      </motion.button>

      {/* 展开内容 */}
      <AnimatePresence>
        {isExpanded && hasData && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-2 ml-6 mr-2 p-4 bg-slate-50 rounded-xl border border-slate-200">
              <NodeDetailContent 
                node={node} 
                data={data} 
                copySQL={copySQL}
                copiedSql={copiedSql}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// 节点详情内容
function NodeDetailContent({ node, data, copySQL, copiedSql }: { 
  node: NodeConfig; 
  data: any;
  copySQL: (sql: string) => void;
  copiedSql: boolean;
}) {
  // 意图解析详情
  if (node.key === "intent" && data) {
    return (
      <div className="grid grid-cols-3 gap-4">
        <DetailItem label="数据集" value={data.dataset} highlight />
        <DetailItem label="查询模式" value={data.query_mode} highlight />
        <DetailItem label="指标" value={data.metrics?.join(", ") || "默认指标"} />
        {data.filters?.date_range && (
          <DetailItem 
            label="日期范围" 
            value={`${data.filters.date_range[0]} ~ ${data.filters.date_range[1]}`} 
            className="col-span-3"
          />
        )}
      </div>
    );
  }

  // SQL步骤详情
  if (data?.result) {
    const isSQL = node.key === "llm_parse" || node.key === "sql_fix" || node.key === "final_sql";
    
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-500">
            {isSQL ? "生成的SQL" : "处理结果"}
          </span>
          {isSQL && (
            <button
              onClick={() => copySQL(data.result)}
              className="flex items-center gap-1.5 px-2 py-1 text-xs text-slate-600 hover:text-slate-800 hover:bg-slate-200 rounded-md transition-colors"
            >
              {copiedSql ? (
                <>
                  <Check className="h-3 w-3 text-emerald-500" />
                  <span className="text-emerald-600">已复制</span>
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" />
                  <span>复制</span>
                </>
              )}
            </button>
          )}
        </div>
        <pre className={cn(
          "text-xs whitespace-pre-wrap break-all font-mono p-3 rounded-lg border",
          "bg-white border-slate-200 text-slate-700",
          "max-h-64 overflow-auto"
        )}>
          {data.result}
        </pre>
      </div>
    );
  }

  return (
    <div className="text-sm text-slate-500">暂无详细数据</div>
  );
}

// 详情项组件
function DetailItem({ label, value, highlight, className }: { 
  label: string; 
  value: string; 
  highlight?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <span className="text-xs text-slate-500 block mb-1">{label}</span>
      <span className={cn(
        "font-medium text-sm",
        highlight ? "text-blue-600" : "text-slate-700"
      )}>
        {value || "-"}
      </span>
    </div>
  );
}

// 数据查询结果组件
function DataQueryResult({ 
  dataQuery, 
  viewMode, 
  onViewModeChange 
}: { 
  dataQuery: QueryContext["dataQuery"]; 
  viewMode: "chart" | "table";
  onViewModeChange: (mode: "chart" | "table") => void;
}) {
  if (!dataQuery) return null;

  const { columns, rows, row_count, chart_config } = dataQuery;
  const hasData = rows && rows.length > 0;

  // 转换数据格式
  const tableData = rows?.map(row => {
    if (Array.isArray(row)) {
      const obj: Record<string, any> = {};
      columns.forEach((col, i) => {
        obj[col] = row[i];
      });
      return obj;
    }
    return row;
  }) || [];

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-white overflow-hidden">
      {/* 标题栏 */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          <span className="font-medium text-sm text-slate-700">执行SQL查询</span>
          <span className="text-xs text-slate-500 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full">
            {row_count || rows?.length || 0} 条记录
          </span>
        </div>
        
        {hasData && (
          <div className="flex items-center gap-2 bg-white rounded-lg border border-slate-200 p-1">
            <button
              onClick={() => onViewModeChange("chart")}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors",
                viewMode === "chart" 
                  ? "bg-blue-100 text-blue-700" 
                  : "text-slate-600 hover:bg-slate-100"
              )}
            >
              <BarChart2 className="h-3.5 w-3.5" />
              图表
            </button>
            <button
              onClick={() => onViewModeChange("table")}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors",
                viewMode === "table" 
                  ? "bg-blue-100 text-blue-700" 
                  : "text-slate-600 hover:bg-slate-100"
              )}
            >
              <Table2 className="h-3.5 w-3.5" />
              表格
            </button>
          </div>
        )}
      </div>

      {/* 内容区域 */}
      <div className="p-4">
        {!hasData ? (
          <div className="flex flex-col items-center justify-center py-8 text-slate-500">
            <AlertCircle className="h-8 w-8 mb-2 text-slate-400" />
            <span className="text-sm">查询结果为空</span>
          </div>
        ) : viewMode === "chart" ? (
          <DataChart data={tableData} columns={columns} chartConfig={chart_config} />
        ) : (
          <DataTable data={tableData} columns={columns} />
        )}
      </div>
    </div>
  );
}

// 数据图表
function DataChart({ data, columns, chartConfig }: { 
  data: Record<string, any>[]; 
  columns: string[];
  chartConfig?: any;
}) {
  const xDataKey = chartConfig?.xDataKey || columns[0];
  const yDataKeys = columns.filter(col => col !== xDataKey).slice(0, 3);
  const ChartType = chartConfig?.type === "line" ? LineChart : BarChart;

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ChartType data={data} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis 
          dataKey={xDataKey} 
          tick={{ fontSize: 11, fill: "#64748b" }} 
          stroke="#cbd5e1" 
          tickLine={{ stroke: "#cbd5e1" }}
        />
        <YAxis 
          tick={{ fontSize: 11, fill: "#64748b" }} 
          stroke="#cbd5e1"
          tickLine={{ stroke: "#cbd5e1" }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            fontSize: "12px",
            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
          }}
        />
        <Legend 
          wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }} 
        />
        {yDataKeys.map((key, index) => (
          chartConfig?.type === "line" ? (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={CHART_COLORS[index % CHART_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 4, fill: "#fff", strokeWidth: 2 }}
              activeDot={{ r: 6 }}
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
      </ChartType>
    </ResponsiveContainer>
  );
}

// 数据表格
function DataTable({ data, columns }: { data: Record<string, any>[]; columns: string[] }) {
  return (
    <div className="overflow-auto max-h-80 rounded-lg border border-slate-200">
      <table className="w-full text-sm">
        <thead className="bg-gradient-to-b from-slate-50 to-slate-100 sticky top-0">
          <tr>
            {columns.map((col) => (
              <th 
                key={col} 
                className="px-4 py-3 text-left font-semibold text-slate-600 whitespace-nowrap border-b border-slate-200"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.slice(0, 50).map((row, i) => (
            <tr 
              key={i} 
              className={cn(
                "transition-colors",
                i % 2 === 0 ? "bg-white" : "bg-slate-50/50",
                "hover:bg-blue-50/50"
              )}
            >
              {columns.map((col) => (
                <td 
                  key={col} 
                  className="px-4 py-2.5 text-slate-600 whitespace-nowrap"
                >
                  {formatValue(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > 50 && (
        <div className="text-center text-xs text-slate-500 py-2 bg-slate-50 border-t border-slate-200">
          显示前 50 条，共 {data.length} 条数据
        </div>
      )}
    </div>
  );
}

// 相似问题推荐
function SimilarQuestionsSection({ 
  questions, 
  onSelect 
}: { 
  questions: string[]; 
  onSelect?: (q: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="mt-4 rounded-xl border border-amber-200 bg-gradient-to-b from-amber-50 to-white overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-amber-100/50 transition-colors"
      >
        <div className="p-1.5 rounded-lg bg-amber-100">
          <Lightbulb className="h-4 w-4 text-amber-600" />
        </div>
        <span className="font-medium text-sm text-amber-800">推荐问题</span>
        <span className="text-xs text-amber-600 px-2 py-0.5 bg-amber-100 rounded-full">
          {questions.length}
        </span>
        <motion.div
          animate={{ rotate: isExpanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="ml-auto"
        >
          <ChevronDown className="h-4 w-4 text-amber-500" />
        </motion.div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="px-4 pb-4 space-y-2">
              {questions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => onSelect?.(q)}
                  className="flex items-start gap-2 w-full text-left p-3 rounded-lg bg-white border border-amber-100 text-sm text-slate-600 hover:border-amber-300 hover:bg-amber-50/50 hover:text-amber-800 transition-all"
                >
                  <MessageCircle className="h-4 w-4 mt-0.5 flex-shrink-0 text-amber-500" />
                  <span>{q}</span>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// 格式化单元格值
function formatValue(value: any): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") {
    return value.toLocaleString("zh-CN", { 
      minimumFractionDigits: 0, 
      maximumFractionDigits: 2 
    });
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export default QueryPipeline;
