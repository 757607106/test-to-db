/**
 * 数据洞察展示组件
 * 
 * 展示 AI 分析生成的业务洞察，包括：
 * - 摘要（一句话总结）
 * - 结构化洞察（趋势/异常/指标/对比）
 * - 业务建议
 */
import { useState, memo } from "react";
import {
  Lightbulb,
  TrendingUp,
  AlertTriangle,
  BarChart3,
  GitCompare,
  ChevronDown,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { InsightEvent, InsightItem } from "@/types/stream-events";

interface InsightDisplayProps {
  insight: InsightEvent;
}

// 洞察类型图标映射
const INSIGHT_ICONS: Record<InsightItem["type"], React.ReactNode> = {
  trend: <TrendingUp className="h-4 w-4 text-blue-500" />,
  anomaly: <AlertTriangle className="h-4 w-4 text-amber-500" />,
  metric: <BarChart3 className="h-4 w-4 text-emerald-500" />,
  comparison: <GitCompare className="h-4 w-4 text-purple-500" />,
};

// 洞察类型标签映射
const INSIGHT_LABELS: Record<InsightItem["type"], string> = {
  trend: "趋势",
  anomaly: "异常",
  metric: "指标",
  comparison: "对比",
};

// 洞察类型颜色映射
const INSIGHT_COLORS: Record<InsightItem["type"], string> = {
  trend: "bg-blue-50 border-blue-200 text-blue-700",
  anomaly: "bg-amber-50 border-amber-200 text-amber-700",
  metric: "bg-emerald-50 border-emerald-200 text-emerald-700",
  comparison: "bg-purple-50 border-purple-200 text-purple-700",
};

export const InsightDisplay = memo(function InsightDisplay({ insight }: InsightDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // 如果没有洞察数据，不渲染
  if (!insight || (!insight.summary && insight.insights.length === 0)) {
    return null;
  }

  const hasDetails = insight.insights.length > 0 || insight.recommendations.length > 0;

  return (
    <div className="mb-4 rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
      {/* 头部 - 摘要区域 */}
      <button
        onClick={() => hasDetails && setIsExpanded(!isExpanded)}
        className={cn(
          "w-full flex items-start justify-between px-4 py-3 bg-gradient-to-r from-indigo-50 to-violet-50 border-b border-slate-200 transition-colors text-left",
          hasDetails && "hover:bg-indigo-50/80 cursor-pointer"
        )}
        disabled={!hasDetails}
      >
        <div className="flex items-start gap-3 flex-1">
          <div className="mt-0.5 p-1.5 bg-indigo-100 rounded-lg">
            <Lightbulb className="h-4 w-4 text-indigo-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-medium text-sm text-slate-700">AI 洞察</span>
              {insight.insights.length > 0 && (
                <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full">
                  {insight.insights.length} 个发现
                </span>
              )}
            </div>
            <p className="text-sm text-slate-600 leading-relaxed">
              {insight.summary || "正在分析数据..."}
            </p>
          </div>
        </div>

        {hasDetails && (
          <div
            className="ml-2 mt-1 transition-transform duration-200"
            style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
          >
            <ChevronDown className="h-4 w-4 text-slate-400" />
          </div>
        )}
      </button>

      {/* 展开区域 - 详细洞察和建议 */}
      {isExpanded && hasDetails && (
        <div className="p-4 space-y-4">
              {/* 结构化洞察 */}
              {insight.insights.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    核心洞察
                  </h4>
                  <div className="space-y-2">
                    {insight.insights.map((item, index) => (
                      <div
                        key={index}
                        className={cn(
                          "flex items-start gap-3 p-3 rounded-lg border",
                          INSIGHT_COLORS[item.type]
                        )}
                      >
                        <div className="mt-0.5">
                          {INSIGHT_ICONS[item.type]}
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="text-xs font-medium uppercase tracking-wide opacity-75">
                            {INSIGHT_LABELS[item.type]}
                          </span>
                          <p className="text-sm mt-0.5 leading-relaxed">
                            {item.description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 业务建议 */}
              {insight.recommendations.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" />
                    业务建议
                  </h4>
                  <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                    <ul className="space-y-2">
                      {insight.recommendations.map((rec, index) => (
                        <li
                          key={index}
                          className="flex items-start gap-2 text-sm text-slate-600"
                        >
                          <span className="flex-shrink-0 w-5 h-5 bg-slate-200 text-slate-600 rounded-full flex items-center justify-center text-xs font-medium">
                            {index + 1}
                          </span>
                          <span className="leading-relaxed">{rec}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* 分析耗时（可选显示） */}
              {insight.time_ms > 0 && (
                <div className="text-xs text-slate-400 text-right">
                  分析耗时: {insight.time_ms}ms
                </div>
              )}
        </div>
      )}
    </div>
  );
});

export default InsightDisplay;
