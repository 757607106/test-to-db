/**
 * 规划执行过程组件 (Planning & Execution Process)
 * 
 * 类似 Cursor/ChatGPT 的思考过程展示：
 * 1. 执行进度条 (sqlSteps) - 显示各阶段状态
 * 2. 推理链 (thoughts) - 显示 AI 的思考过程
 * 3. 阶段消息 (stageMessages) - 显示详细执行信息
 * 4. 缓存命中提示 (cacheHit) - 显示是否命中缓存
 * 
 * 设计原则：
 * - 固定高度避免页面跳动
 * - 平滑过渡动画
 * - 状态变化不引起布局抖动
 */
import { useState, memo, useMemo } from "react";
import { cn } from "@/lib/utils";
import {
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  Target,
  ArrowRight,
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  Zap,
  Database,
  Code2,
  PlayCircle,
  BarChart3,
  RefreshCcw,
  MessageSquare,
  Clock,
} from "lucide-react";
import type { 
  QueryContext, 
  SQLStepEvent, 
  StageMessageEvent, 
  ThoughtEvent,
  CacheHitEvent 
} from "@/types/stream-events";
import { SQL_STEP_LABELS, CACHE_HIT_LABELS } from "@/types/stream-events";

interface ThinkingProcessProps {
  queryContext: QueryContext;
  isLoading: boolean;
}

// 步骤图标映射
const STEP_ICONS: Record<string, React.ReactNode> = {
  schema_agent: <Database className="h-3.5 w-3.5" />,
  clarification: <MessageSquare className="h-3.5 w-3.5" />,
  sql_generator: <Code2 className="h-3.5 w-3.5" />,
  sql_executor: <PlayCircle className="h-3.5 w-3.5" />,
  data_analyst: <BarChart3 className="h-3.5 w-3.5" />,
  chart_generator: <BarChart3 className="h-3.5 w-3.5" />,
  error_recovery: <RefreshCcw className="h-3.5 w-3.5" />,
  general_chat: <MessageSquare className="h-3.5 w-3.5" />,
  // 兼容旧版
  schema_mapping: <Database className="h-3.5 w-3.5" />,
  few_shot: <Zap className="h-3.5 w-3.5" />,
  llm_parse: <Code2 className="h-3.5 w-3.5" />,
  sql_fix: <RefreshCcw className="h-3.5 w-3.5" />,
  final_sql: <PlayCircle className="h-3.5 w-3.5" />,
};

// 步骤状态颜色
const STATUS_COLORS = {
  pending: "text-slate-400 bg-slate-100",
  running: "text-blue-600 bg-blue-100 animate-pulse",
  completed: "text-emerald-600 bg-emerald-100",
  error: "text-red-600 bg-red-100",
  skipped: "text-slate-400 bg-slate-50",
};

// 步骤状态图标
const STATUS_ICONS = {
  pending: <Circle className="h-3 w-3" />,
  running: <Loader2 className="h-3 w-3 animate-spin" />,
  completed: <CheckCircle2 className="h-3 w-3" />,
  error: <AlertCircle className="h-3 w-3" />,
  skipped: <Circle className="h-3 w-3 opacity-50" />,
};

/**
 * 缓存命中提示
 */
const CacheHitBadge = memo(function CacheHitBadge({ cacheHit }: { cacheHit: CacheHitEvent }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-amber-50 to-yellow-50 rounded-lg border border-amber-200">
      <Zap className="h-3.5 w-3.5 text-amber-600" />
      <span className="text-xs font-medium text-amber-700">
        {CACHE_HIT_LABELS[cacheHit.hit_type] || "缓存命中"}
      </span>
      {cacheHit.similarity < 1 && (
        <span className="text-xs text-amber-600">
          ({Math.round(cacheHit.similarity * 100)}% 匹配)
        </span>
      )}
      <span className="text-xs text-amber-500">
        {cacheHit.time_ms}ms
      </span>
    </div>
  );
});

/**
 * 执行进度条 - 水平步骤展示
 */
const ExecutionProgress = memo(function ExecutionProgress({ 
  steps, 
  isLoading 
}: { 
  steps: SQLStepEvent[];
  isLoading: boolean;
}) {
  // 按照执行顺序排序步骤 - useMemo 必须在任何 return 之前
  const orderedSteps = useMemo(() => {
    if (!steps || steps.length === 0) return [];
    const stepOrder = [
      'schema_agent', 'clarification', 'sql_generator', 'sql_executor',
      'data_analyst', 'chart_generator', 'error_recovery',
      // 兼容旧版
      'schema_mapping', 'few_shot', 'llm_parse', 'sql_fix', 'final_sql'
    ];
    return [...steps].sort((a, b) => {
      const indexA = stepOrder.indexOf(a.step);
      const indexB = stepOrder.indexOf(b.step);
      return (indexA === -1 ? 999 : indexA) - (indexB === -1 ? 999 : indexB);
    });
  }, [steps]);

  // 计算完成进度
  const progress = useMemo(() => {
    if (!steps || steps.length === 0) return 0;
    const completed = steps.filter(s => s.status === 'completed').length;
    return Math.round((completed / steps.length) * 100);
  }, [steps]);

  // 无数据时不渲染
  if (!steps || steps.length === 0) return null;

  return (
    <div className="space-y-3">
      {/* 进度条 */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div 
            className={cn(
              "h-full rounded-full transition-all duration-500",
              isLoading ? "bg-blue-500" : "bg-emerald-500"
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-xs font-medium text-slate-500 min-w-[3rem] text-right">
          {progress}%
        </span>
      </div>

      {/* 步骤列表 */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {orderedSteps.map((step, index) => (
          <div key={`${step.step}-${index}`} className="flex items-center">
            <div
              className={cn(
                "flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-all",
                STATUS_COLORS[step.status as keyof typeof STATUS_COLORS] || STATUS_COLORS.pending
              )}
              title={step.result || SQL_STEP_LABELS[step.step] || step.step}
            >
              {STEP_ICONS[step.step] || <Circle className="h-3.5 w-3.5" />}
              <span className="whitespace-nowrap">
                {SQL_STEP_LABELS[step.step] || step.step}
              </span>
              {STATUS_ICONS[step.status as keyof typeof STATUS_ICONS] || STATUS_ICONS.pending}
            </div>
            {index < orderedSteps.length - 1 && (
              <ArrowRight className="h-3 w-3 text-slate-300 mx-1 flex-shrink-0" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
});

/**
 * 推理链展示
 */
const ReasoningChain = memo(function ReasoningChain({ 
  thoughts,
  isExpanded,
  onToggle
}: { 
  thoughts: ThoughtEvent[];
  isExpanded: boolean;
  onToggle: () => void;
}) {
  if (!thoughts || thoughts.length === 0) return null;

  return (
    <div className="border-t border-slate-100 pt-3">
      <button
        onClick={onToggle}
        className="flex items-center gap-2 text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors"
      >
        <BrainCircuit className="h-3.5 w-3.5" />
        <span>推理过程 ({thoughts.length})</span>
        {isExpanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
      </button>

      {isExpanded && (
        <div className="mt-3 space-y-3 animate-in fade-in slide-in-from-top-1 duration-200">
          {thoughts.map((item, idx) => (
            <div 
              key={idx} 
              className="relative pl-4 border-l-2 border-slate-200 py-1"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <Target className="h-3 w-3 text-blue-500" />
                <span className="text-[11px] font-bold text-blue-600 uppercase">
                  {SQL_STEP_LABELS[item.agent as keyof typeof SQL_STEP_LABELS] || item.agent}
                </span>
                {item.time_ms > 0 && (
                  <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                    <Clock className="h-2.5 w-2.5" />
                    {item.time_ms}ms
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-700 leading-relaxed mb-2">
                {item.thought}
              </p>
              {item.plan && (
                <div className="flex items-start gap-2 bg-white/50 p-2 rounded-lg border border-slate-100">
                  <ArrowRight className="h-3 w-3 text-emerald-500 mt-1 flex-shrink-0" />
                  <div className="text-xs text-slate-500 italic">
                    <span className="font-semibold text-emerald-600 not-italic mr-1">计划:</span>
                    {item.plan}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

/**
 * 阶段消息展示
 */
const StageMessages = memo(function StageMessages({ 
  messages,
  isExpanded,
  onToggle
}: { 
  messages: StageMessageEvent[];
  isExpanded: boolean;
  onToggle: () => void;
}) {
  if (!messages || messages.length === 0) return null;

  // 只显示最近的5条消息
  const recentMessages = messages.slice(-5);

  return (
    <div className="border-t border-slate-100 pt-3">
      <button
        onClick={onToggle}
        className="flex items-center gap-2 text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors"
      >
        <MessageSquare className="h-3.5 w-3.5" />
        <span>执行日志 ({messages.length})</span>
        {isExpanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
      </button>

      {isExpanded && (
        <div className="mt-3 space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
          {recentMessages.map((msg, idx) => (
            <div 
              key={idx}
              className="flex items-start gap-2 text-xs"
            >
              <span className="text-slate-400 whitespace-nowrap">
                {msg.step ? `[${SQL_STEP_LABELS[msg.step] || msg.step}]` : '[系统]'}
              </span>
              <span className="text-slate-600 flex-1">
                {msg.message}
              </span>
              {msg.time_ms > 0 && (
                <span className="text-slate-400 whitespace-nowrap">
                  {msg.time_ms}ms
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

/**
 * 规划执行过程主组件
 */
export const ThinkingProcess = memo(function ThinkingProcess({ 
  queryContext, 
  isLoading 
}: ThinkingProcessProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showThoughts, setShowThoughts] = useState(false);
  const [showMessages, setShowMessages] = useState(false);

  const { cacheHit, sqlSteps, thoughts, stageMessages } = queryContext;

  // 计算总耗时 - useMemo 必须在任何 return 之前
  const totalTime = useMemo(() => {
    let time = 0;
    if (sqlSteps) {
      time += sqlSteps.reduce((acc, s) => acc + (s.time_ms || 0), 0);
    }
    if (thoughts) {
      time += thoughts.reduce((acc, t) => acc + (t.time_ms || 0), 0);
    }
    return time;
  }, [sqlSteps, thoughts]);

  // 计算完成状态
  const isCompleted = useMemo(() => {
    if (!sqlSteps || sqlSteps.length === 0) return false;
    return sqlSteps.every(s => s.status === 'completed' || s.status === 'error' || s.status === 'skipped');
  }, [sqlSteps]);

  // 如果没有任何数据，不渲染
  const hasContent = (sqlSteps && sqlSteps.length > 0) || 
                     (thoughts && thoughts.length > 0) || 
                     (stageMessages && stageMessages.length > 0) ||
                     cacheHit;

  if (!hasContent) return null;

  // 根据状态决定显示文案
  const headerText = isLoading 
    ? "规划执行中..." 
    : (isCompleted ? "执行完成" : "规划执行");

  return (
    <div className={cn(
      "mb-4 rounded-xl border overflow-hidden",
      // 使用 min-height 避免高度变化导致的跳动
      "min-h-[60px]",
      // 移除 transition-all，只对特定属性过渡
      "transition-colors duration-300",
      isLoading 
        ? "border-blue-200 bg-blue-50/30" 
        : (isCompleted ? "border-emerald-200 bg-emerald-50/30" : "border-slate-200 bg-slate-50/50")
    )}>
      {/* 头部 - 固定高度 */}
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between px-4 py-2.5 hover:bg-slate-100/50 transition-colors h-[44px]"
      >
        <div className="flex items-center gap-2">
          <BrainCircuit className={cn(
            "h-4 w-4 transition-colors duration-300",
            isLoading ? "text-blue-500 animate-pulse" : (isCompleted ? "text-emerald-500" : "text-slate-500")
          )} />
          <span className={cn(
            "text-xs font-semibold uppercase tracking-wider transition-colors duration-300",
            isLoading ? "text-blue-600" : (isCompleted ? "text-emerald-600" : "text-slate-600")
          )}>
            {headerText}
          </span>
          {totalTime > 0 && !isLoading && (
            <span className="text-xs text-slate-400">
              · {totalTime > 1000 ? `${(totalTime / 1000).toFixed(1)}s` : `${totalTime}ms`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {cacheHit && (
            <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full">
              缓存
            </span>
          )}
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
          )}
        </div>
      </button>

      {/* 展开内容 - 使用 grid 实现平滑展开/收起 */}
      <div className={cn(
        "grid transition-[grid-template-rows] duration-300 ease-in-out",
        isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
      )}>
        <div className="overflow-hidden">
          <div className="px-4 pb-4 space-y-4">
            {/* 缓存命中提示 */}
            {cacheHit && <CacheHitBadge cacheHit={cacheHit} />}

            {/* 执行进度 */}
            {sqlSteps && sqlSteps.length > 0 && (
              <ExecutionProgress steps={sqlSteps} isLoading={isLoading} />
            )}

            {/* 推理链 */}
            {thoughts && thoughts.length > 0 && (
              <ReasoningChain 
                thoughts={thoughts} 
                isExpanded={showThoughts}
                onToggle={() => setShowThoughts(!showThoughts)}
              />
            )}

            {/* 阶段消息 */}
            {stageMessages && stageMessages.length > 0 && (
              <StageMessages 
                messages={stageMessages}
                isExpanded={showMessages}
                onToggle={() => setShowMessages(!showMessages)}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

export default ThinkingProcess;
