/**
 * SQL生成步骤组件
 * 
 * 展示SQL生成的各个步骤及其状态
 */
import { useState, useMemo } from "react";
import { CheckCircle2, Circle, Loader2, XCircle, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SQLStepEvent } from "@/types/stream-events";
import { SQL_STEP_LABELS } from "@/types/stream-events";

interface SQLGenerationStepsProps {
  steps: SQLStepEvent[];
}

// 所有步骤的顺序
const STEP_ORDER = ["schema_mapping", "few_shot", "llm_parse", "sql_fix", "final_sql"];

export function SQLGenerationSteps({ steps }: SQLGenerationStepsProps) {
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  // 计算总耗时
  const totalTime = useMemo(() => {
    return steps.reduce((sum, step) => sum + (step.time_ms || 0), 0);
  }, [steps]);

  // 获取步骤状态图标
  const getStatusIcon = (status: string) => {
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

  // 获取步骤样式
  const getStepStyle = (status: string | undefined) => {
    switch (status) {
      case "completed":
        return "bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800";
      case "running":
        return "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800 animate-pulse";
      case "error":
        return "bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800";
      default:
        return "bg-slate-50 text-slate-500 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700";
    }
  };

  // 检查是否有任何完成的步骤
  const hasCompletedSteps = steps.some(s => s.status === "completed");

  if (steps.length === 0) return null;

  return (
    <div className="rounded-lg border bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      {/* 头部 */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100 dark:border-slate-800">
        {hasCompletedSteps ? (
          <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
        ) : (
          <Loader2 className="h-4 w-4 text-blue-500 animate-spin flex-shrink-0" />
        )}
        <span className="font-medium text-slate-700 dark:text-slate-200">SQL生成</span>
        <span className="text-muted-foreground text-sm">(耗时: {totalTime}ms)</span>
      </div>

      {/* 步骤列表 */}
      <div className="p-4">
        <div className="flex flex-wrap gap-2">
          {STEP_ORDER.map((stepKey) => {
            const step = steps.find(s => s.step === stepKey);
            const label = SQL_STEP_LABELS[stepKey] || stepKey;
            const isExpanded = expandedStep === stepKey;

            return (
              <button
                key={stepKey}
                onClick={() => setExpandedStep(isExpanded ? null : stepKey)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-sm border flex items-center gap-1.5 transition-all",
                  getStepStyle(step?.status)
                )}
              >
                {step && getStatusIcon(step.status)}
                {label}
                {step?.result && (
                  isExpanded ? (
                    <ChevronDown className="h-3 w-3 ml-1" />
                  ) : (
                    <ChevronRight className="h-3 w-3 ml-1" />
                  )
                )}
              </button>
            );
          })}
        </div>

        {/* 展开的步骤详情 */}
        {expandedStep && (
          <div className="mt-3">
            {steps.filter(s => s.step === expandedStep).map((step, idx) => (
              <div
                key={idx}
                className="bg-slate-50 dark:bg-slate-800 rounded-md p-3"
              >
                {step.result && (
                  <pre className="text-xs text-slate-600 dark:text-slate-300 whitespace-pre-wrap break-all font-mono">
                    {step.result}
                  </pre>
                )}
                {step.time_ms > 0 && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    耗时: {step.time_ms}ms
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
