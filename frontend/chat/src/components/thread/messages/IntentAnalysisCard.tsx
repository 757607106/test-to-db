/**
 * 意图解析卡片组件
 * 
 * 展示用户查询的意图解析结果
 */
import { useState } from "react";
import { CheckCircle2, RefreshCw, ChevronDown, ChevronRight, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { IntentAnalysisEvent } from "@/types/stream-events";

interface IntentAnalysisCardProps {
  data: IntentAnalysisEvent;
  onRequery?: () => void;
}

export function IntentAnalysisCard({ data, onRequery }: IntentAnalysisCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className="rounded-lg border bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      {/* 头部 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
      >
        <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
        <span className="font-medium text-slate-700 dark:text-slate-200">意图解析</span>
        <span className="text-muted-foreground text-sm">(耗时: {data.time_ms}ms)</span>
        <div className="ml-auto">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-slate-400" />
          )}
        </div>
      </button>

      {/* 内容 */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-slate-100 dark:border-slate-800">
          <div className="pt-3 space-y-3">
            {/* 基础信息网格 */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              <div className="flex flex-col">
                <span className="text-muted-foreground text-xs mb-1">数据集</span>
                <span className="text-blue-600 dark:text-blue-400 font-medium">
                  {data.dataset}
                </span>
              </div>
              <div className="flex flex-col">
                <span className="text-muted-foreground text-xs mb-1">查询模式</span>
                <span className="text-blue-600 dark:text-blue-400 font-medium">
                  {data.query_mode}
                </span>
              </div>
              <div className="flex flex-col">
                <span className="text-muted-foreground text-xs mb-1">指标</span>
                <span className="text-blue-600 dark:text-blue-400 font-medium">
                  {data.metrics.join(", ") || "无"}
                </span>
              </div>
            </div>

            {/* 筛选条件 */}
            {data.filters.date_range && (
              <div className="flex items-center gap-2 text-sm bg-slate-50 dark:bg-slate-800 rounded-md px-3 py-2">
                <span className="text-muted-foreground flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5" />
                  筛选条件:
                </span>
                <span className="text-slate-600 dark:text-slate-300">数据时间:</span>
                <span className="text-blue-600 dark:text-blue-400 font-medium">
                  {data.filters.date_range[0]}
                </span>
                <span className="text-slate-400">→</span>
                <span className="text-blue-600 dark:text-blue-400 font-medium">
                  {data.filters.date_range[1]}
                </span>
              </div>
            )}

            {/* 重新查询按钮 */}
            {onRequery && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRequery}
                className="mt-2"
              >
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                重新查询
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
