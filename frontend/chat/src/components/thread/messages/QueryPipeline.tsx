/**
 * 统一查询流程管线组件
 * 
 * 整合所有工具调用，展示完整的执行流程
 * 支持点击展开查看详细数据
 * 
 * 已对齐后端 Hub-and-Spoke 架构
 */
import React, { useState, useMemo } from "react";
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
  Clock,
  Copy,
  Check,
  History,
  Zap,
  HardDrive,
  Terminal,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { QueryContext } from "@/types/stream-events";
import { CACHE_HIT_LABELS } from "@/types/stream-events";
import { DataChartDisplay } from "./DataChartDisplay";
import { DataQueryResult } from "./DataQueryResult";
import { DataAnalysisDisplay } from "./DataAnalysisDisplay";
import { 
  PIPELINE_NODES, 
  STATUS_CONFIG, 
  findNodeByStep, 
  isCompletedStep,
  type NodeConfig, 
  type NodeStatus 
} from "./query-pipeline/nodes-config";

// 缓存命中配置
const CACHE_HIT_CONFIG = {
  thread_history: { icon: History, color: "purple", bg: "from-purple-50 to-purple-100/50" },
  exact: { icon: HardDrive, color: "emerald", bg: "from-emerald-50 to-emerald-100/50" },
  semantic: { icon: Zap, color: "blue", bg: "from-blue-50 to-blue-100/50" },
};

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

// 节点详情内容
const NodeDetailContent = React.memo(function NodeDetailContent({ node, data, copySQL, copiedSql }: { 
  node: NodeConfig; 
  data: any;
  copySQL: (sql: string) => void;
  copiedSql: boolean;
}) {
  // 意图解析详情
  if (node.key === "intent" && data) {
    return (
      <div className="space-y-4">
        {/* 工具调用信息 */}
        <div className="flex items-center gap-2 pb-3 border-b border-slate-200">
          <Terminal className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-mono text-slate-500">调用工具: {node.toolName}</span>
          <span className="text-xs text-emerald-600 ml-auto">调用成功</span>
        </div>
        
        {/* 解析结果 */}
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
        
        {/* 原始返回 */}
        <div className="pt-3 border-t border-slate-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500">原始返回消息</span>
            <button
              onClick={() => copySQL(JSON.stringify(data, null, 2))}
              className="flex items-center gap-1 px-2 py-1 text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-200 rounded transition-colors"
            >
              {copiedSql ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
              <span>{copiedSql ? "已复制" : "复制"}</span>
            </button>
          </div>
          <pre className="text-xs font-mono text-slate-600 bg-white border border-slate-200 rounded-lg p-3 max-h-40 overflow-auto">
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      </div>
    );
  }

  // Schema 映射详情 - 显示表和列信息
  if (node.key === "schema_mapping" && data?.result) {
    try {
      const schemaData = JSON.parse(data.result);
      if (schemaData.tables && Array.isArray(schemaData.tables) && schemaData.tables.length > 0) {
        return (
          <div className="space-y-4">
            {/* 工具调用信息 */}
            <div className="flex items-center gap-2 pb-3 border-b border-slate-200">
              <Terminal className="h-4 w-4 text-slate-400" />
              <span className="text-xs font-mono text-slate-500">调用工具: {node.toolName}</span>
              <span className="text-xs text-emerald-600 ml-auto">调用成功</span>
            </div>
            
            {schemaData.summary && (
              <div className="text-sm font-medium text-slate-700 mb-3">
                {schemaData.summary}
              </div>
            )}
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {schemaData.tables.map((table: any, idx: number) => {
                const tableName = table.name || table.table_name || `表${idx + 1}`;
                const tableComment = table.comment || table.table_comment || "";
                const columns = table.columns || [];
                
                return (
                  <div key={idx} className="bg-white rounded-lg border border-slate-200 p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Database className="h-4 w-4 text-blue-600 flex-shrink-0" />
                      <span className="font-semibold text-sm text-slate-800">{tableName}</span>
                      {tableComment && (
                        <span className="text-xs text-slate-500">- {tableComment}</span>
                      )}
                    </div>
                    {columns.length > 0 && (
                      <div className="grid grid-cols-2 gap-2 mt-2 pl-6">
                        {columns.slice(0, 20).map((col: any, colIdx: number) => {
                          const colName = col.name || col.column_name || "";
                          const colType = col.type || col.data_type || "";
                          const colComment = col.comment || col.column_comment || "";
                          
                          return (
                            <div key={colIdx} className="flex items-start gap-2 text-xs">
                              <span className="text-slate-600 font-mono">{colName}</span>
                              {colType && <span className="text-slate-400">({colType})</span>}
                              {colComment && (
                                <span className="text-slate-500 text-[10px] truncate max-w-[100px]" title={colComment}>
                                  // {colComment}
                                </span>
                              )}
                            </div>
                          );
                        })}
                        {columns.length > 20 && (
                          <div className="text-xs text-slate-400 col-span-2">
                            ... 还有 {columns.length - 20} 个列
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      }
      // 如果 tables 为空或格式不对，显示原始 JSON
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-200">
            <Terminal className="h-4 w-4 text-slate-400" />
            <span className="text-xs font-mono text-slate-500">调用工具: {node.toolName}</span>
            <span className="text-xs text-emerald-600 ml-auto">调用成功</span>
          </div>
          <span className="text-xs text-slate-500">原始返回消息</span>
          <pre className={cn(
            "text-xs whitespace-pre-wrap break-all font-mono p-3 rounded-lg border",
            "bg-white border-slate-200 text-slate-700",
            "max-h-64 overflow-auto"
          )}>
            {JSON.stringify(schemaData, null, 2)}
          </pre>
        </div>
      );
    } catch {
      // JSON 解析失败，显示原始文本
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-200">
            <Terminal className="h-4 w-4 text-slate-400" />
            <span className="text-xs font-mono text-slate-500">调用工具: {node.toolName}</span>
            <span className="text-xs text-emerald-600 ml-auto">调用成功</span>
          </div>
          <span className="text-xs text-slate-500">原始返回消息</span>
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
  }

  // SQL步骤详情 - 显示执行结果明细
  if (data?.result) {
    const isSQL = node.key === "llm_parse" || node.key === "sql_fix" || node.key === "final_sql";
    const stepStatus = data.status || "completed";
    
    // 尝试解析 result JSON
    const displayResult = data.result;
    let parsedResult: any = null;
    let isResultJSON = false;
    
    try {
      parsedResult = JSON.parse(data.result);
      if (typeof parsedResult === "object" && parsedResult !== null) {
        isResultJSON = true;
      }
    } catch {
      // 不是 JSON，保持原样
    }
    
    return (
      <div className="space-y-4">
        {/* 工具调用信息 */}
        <div className="flex items-center gap-2 pb-3 border-b border-slate-200">
          <Terminal className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-mono text-slate-500">调用工具: {node.toolName}</span>
          <span className={cn(
            "text-xs ml-auto",
            stepStatus === "completed" ? "text-emerald-600" : 
            stepStatus === "error" ? "text-red-600" : "text-blue-600"
          )}>
            {stepStatus === "completed" ? "调用成功" : stepStatus === "error" ? "调用失败" : "调用中..."}
          </span>
        </div>
        
        {/* 执行结果明细 */}
        {isResultJSON && parsedResult ? (
          <div className="space-y-3">
            {/* 如果是对象，逐字段显示 */}
            {Object.entries(parsedResult).map(([key, value]) => (
              <div key={key} className="space-y-1">
                <span className="text-xs font-medium text-slate-600">{key}</span>
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-3">
                  {typeof value === "object" ? (
                    <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap break-all max-h-40 overflow-auto">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ) : (
                    <span className="text-xs font-mono text-slate-700">{String(value)}</span>
                  )}
                </div>
              </div>
            ))}
            
            {/* 原始 JSON 可折叠查看 */}
            <details className="mt-3">
              <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-700">
                查看原始 JSON
              </summary>
              <div className="mt-2 flex items-center justify-end">
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
              </div>
              <pre className="text-xs font-mono text-slate-600 bg-white border border-slate-200 rounded-lg p-3 max-h-64 overflow-auto mt-2">
                {JSON.stringify(parsedResult, null, 2)}
              </pre>
            </details>
          </div>
        ) : (
          /* 非 JSON 结果（如 SQL）直接显示 */
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-600">
                {isSQL ? "生成的SQL" : "执行结果"}
              </span>
              {displayResult.length > 50 && (
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
              "max-h-64 overflow-auto",
              isSQL ? "bg-slate-900 text-green-400 border-slate-700" : "bg-white border-slate-200 text-slate-700"
            )}>
              {displayResult}
            </pre>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="text-sm text-slate-500">暂无详细数据</div>
  );
});

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

const PipelineNode = React.memo(function PipelineNode({ node, status, data, isExpanded, onToggle, copySQL, copiedSql }: PipelineNodeProps) {
  const Icon = node.icon;
  const hasData = data && (
    (node.key === "intent" && data) ||
    (data.result || data.time_ms > 0)
  );

  const config = STATUS_CONFIG[status];
  const StatusIcon = config.icon;

  // 状态文本
  const statusText = status === "running" 
    ? `正在调用 ${node.toolName}...`
    : status === "completed"
    ? `${node.toolName} 调用成功`
    : status === "error"
    ? `${node.toolName} 调用失败`
    : "等待执行";

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
          <div className="flex items-center gap-2 flex-wrap">
            <Icon className={cn("h-4 w-4", config.text)} />
            <span className={cn("font-medium text-sm", config.text)}>{node.label}</span>
            {/* 工具名称标签 */}
            {node.toolName && (status === "running" || status === "completed" || status === "error") && (
              <span className={cn(
                "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono",
                status === "running" ? "bg-blue-100 text-blue-700" :
                status === "completed" ? "bg-emerald-100 text-emerald-700" :
                "bg-red-100 text-red-700"
              )}>
                <Terminal className="h-2.5 w-2.5" />
                {node.toolName}
              </span>
            )}
            {data?.time_ms > 0 && (
              <span className="text-xs text-slate-400 ml-auto mr-2">{data.time_ms}ms</span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">{statusText}</p>
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
});



// 推荐问题组件
const SimilarQuestions = React.memo(function SimilarQuestions({ 
  questions,
  onSelectQuestion 
}: { 
  questions: string[];
  onSelectQuestion?: (question: string) => void;
}) {
  if (!questions || questions.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
      {/* 标题栏 */}
      <div className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-50 to-pink-50 border-b border-slate-200">
        <Sparkles className="h-4 w-4 text-purple-600" />
        <span className="font-medium text-sm text-slate-700">您可能还想问</span>
      </div>

      {/* 问题列表 */}
      <div className="p-4 space-y-2">
        {questions.map((question, index) => (
          <button
            key={index}
            onClick={() => onSelectQuestion?.(question)}
            className="w-full text-left px-4 py-2.5 rounded-lg bg-slate-50 hover:bg-purple-50 border border-slate-200 hover:border-purple-200 transition-colors group"
          >
            <span className="text-sm text-slate-700 group-hover:text-purple-700">
              {question}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
});

// 缓存命中横幅
const CacheHitBanner = React.memo(function CacheHitBanner({ cacheHit }: { cacheHit: QueryContext["cacheHit"] }) {
  if (!cacheHit) return null;

  const c = CACHE_HIT_CONFIG[cacheHit.hit_type] || CACHE_HIT_CONFIG.semantic;
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
});

interface QueryPipelineProps {
  queryContext: QueryContext;
  onSelectQuestion?: (question: string) => void;
}

export function QueryPipeline({ queryContext, onSelectQuestion }: QueryPipelineProps) {
  // 默认展开，但允许用户折叠
  const [isContainerExpanded, setIsContainerExpanded] = useState(true);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [copiedSql, setCopiedSql] = useState(false);

  // 使用解构避免依赖整个 queryContext
  const { cacheHit, intentAnalysis, sqlSteps, dataQuery, similarQuestions } = queryContext;

  // 创建节点状态映射 - 使用 useMemo 缓存
  const nodeStatesMap = useMemo(() => {
    const map = new Map<string, NodeStatus>();
    
    // 意图解析状态
    map.set("intent", intentAnalysis ? "completed" : "pending");
    
    // SQL 步骤状态 - 使用 findNodeByStep 支持多个 stepKey
    sqlSteps.forEach(step => {
      const node = findNodeByStep(step.step);
      if (node) {
        map.set(node.key, step.status as NodeStatus);
      }
    });
    
    return map;
  }, [intentAnalysis, sqlSteps]);

  // 创建节点数据映射 - 使用 useMemo 缓存
  const nodeDataMap = useMemo(() => {
    const map = new Map<string, any>();
    
    // 意图解析数据
    if (intentAnalysis) {
      map.set("intent", intentAnalysis);
    }
    
    // SQL 步骤数据 - 使用 findNodeByStep 支持多个 stepKey
    sqlSteps.forEach(step => {
      const node = findNodeByStep(step.step);
      if (node) {
        map.set(node.key, step);
      }
    });
    
    return map;
  }, [intentAnalysis, sqlSteps]);

  // 获取节点状态
  const getNodeStatus = (node: NodeConfig): NodeStatus => {
    return nodeStatesMap.get(node.key) || "pending";
  };

  // 获取节点数据
  const getNodeData = (node: NodeConfig): any => {
    return nodeDataMap.get(node.key) || null;
  };

  // 计算总耗时
  const totalTime = useMemo(() => {
    let time = intentAnalysis?.time_ms || 0;
    time += sqlSteps.reduce((sum, step) => sum + (step.time_ms || 0), 0);
    return time;
  }, [intentAnalysis, sqlSteps]);

  // 检查整体状态 - 使用 useMemo 缓存
  const { hasRunningStep, hasError, isCompleted } = useMemo(() => {
    return {
      hasRunningStep: sqlSteps.some(s => s.status === "running"),
      hasError: sqlSteps.some(s => s.status === "error"),
      // 完成条件：使用 isCompletedStep 检查新旧节点名称
      isCompleted: sqlSteps.some((s) => 
        isCompletedStep(s.step) && s.status === "completed"
      ),
    };
  }, [sqlSteps]);

  // 如果状态更新了，但 container 是折叠的，我们是否应该自动展开？
  // 或者是为了避免闪烁，我们需要保持状态稳定。
  // 目前逻辑看起来是稳定的。
  
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
    <div className="space-y-4">
      {/* 工具执行链路面板 */}
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

        {/* 缓存命中提示 */}
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
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 数据表格 */}
      {dataQuery && dataQuery.rows && dataQuery.rows.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <DataQueryResult dataQuery={dataQuery} />
        </motion.div>
      )}

      {/* 智能图表 - 使用统一的 DataChartDisplay */}
      {dataQuery && dataQuery.chart_config && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <DataChartDisplay dataQuery={dataQuery} />
        </motion.div>
      )}

      {/* 数据分析洞察 - 在图表下方显示 */}
      {(() => {
        // 支持新旧节点名称: data_analyst (Hub-and-Spoke) 和 data_analysis (旧版)
        const analysisStep = sqlSteps.find(s => 
          s.step === "data_analyst" || s.step === "data_analysis"
        );
        return analysisStep && analysisStep.status === "completed" && analysisStep.result && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
          >
            <DataAnalysisDisplay analysisStep={analysisStep} />
          </motion.div>
        );
      })()}

      {/* 推荐问题 - 在最后显示 */}
      {similarQuestions && similarQuestions.questions && similarQuestions.questions.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <SimilarQuestions 
            questions={similarQuestions.questions} 
            onSelectQuestion={onSelectQuestion}
          />
        </motion.div>
      )}
    </div>
  );
}

export default QueryPipeline;
