/**
 * AnalystInsightsCard 组件
 * 用于展示数据分析洞察和业务建议
 */
import { useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { cn } from "@/lib/utils";
import {
  TrendingUp,
  AlertTriangle,
  Lightbulb,
  ChevronDown,
  ChevronUp,
  BarChart3,
} from "lucide-react";

export interface AnalystInsights {
  summary?: {
    total_rows?: number;
    key_metrics?: Record<string, any>;
    [key: string]: any;
  };
  trends?: {
    trend_direction?: string;
    total_growth_rate?: number;
    description?: string;
    [key: string]: any;
  };
  anomalies?: Array<{
    column?: string;
    type?: string;
    description?: string;
    [key: string]: any;
  }>;
  recommendations?: Array<{
    type?: string;
    content?: string;
    [key: string]: any;
  }>;
  visualizations?: string[];
}

interface AnalystInsightsCardProps {
  insights: AnalystInsights;
  className?: string;
}

export function AnalystInsightsCard({
  insights,
  className,
}: AnalystInsightsCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const hasSummary = insights.summary && Object.keys(insights.summary).length > 0;
  const hasTrends = insights.trends && Object.keys(insights.trends).length > 0;
  const hasAnomalies = insights.anomalies && insights.anomalies.length > 0;
  const hasRecommendations =
    insights.recommendations && insights.recommendations.length > 0;

  const hasAnyInsights =
    hasSummary || hasTrends || hasAnomalies || hasRecommendations;

  if (!hasAnyInsights) {
    return null;
  }

  return (
    <Card
      className={cn(
        "p-4 mb-4 border-purple-200 bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-950 dark:to-pink-950 dark:border-purple-800",
        className
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-purple-600 dark:text-purple-400" />
          <h3 className="font-semibold text-purple-900 dark:text-purple-100">
            数据分析洞察
          </h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className="h-8 gap-1"
        >
          {isExpanded ? (
            <>
              收起 <ChevronUp className="w-4 h-4" />
            </>
          ) : (
            <>
              展开 <ChevronDown className="w-4 h-4" />
            </>
          )}
        </Button>
      </div>

      {isExpanded && (
        <div className="space-y-4">
          {/* 数据摘要 */}
          {hasSummary && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-purple-200 dark:border-purple-700">
              <h4 className="font-medium text-sm text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                📊 数据摘要
              </h4>
              <div className="space-y-1 text-sm">
                {insights.summary?.total_rows && (
                  <p className="text-gray-700 dark:text-gray-300">
                    总行数: <span className="font-semibold">{insights.summary.total_rows}</span>
                  </p>
                )}
                {insights.summary?.key_metrics &&
                  Object.entries(insights.summary.key_metrics)
                    .slice(0, 5)
                    .map(([key, value]) => (
                      <p
                        key={key}
                        className="text-gray-700 dark:text-gray-300"
                      >
                        {key}:{" "}
                        <span className="font-semibold">
                          {typeof value === "number"
                            ? value.toLocaleString()
                            : value}
                        </span>
                      </p>
                    ))}
              </div>
            </div>
          )}

          {/* 趋势分析 */}
          {hasTrends && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-green-200 dark:border-green-700">
              <h4 className="font-medium text-sm text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-600 dark:text-green-400" />
                趋势分析
              </h4>
              <div className="space-y-1 text-sm">
                {insights.trends?.description && (
                  <p className="text-gray-700 dark:text-gray-300">
                    {insights.trends.description}
                  </p>
                )}
                {insights.trends?.trend_direction && (
                  <p className="text-gray-700 dark:text-gray-300">
                    趋势方向:{" "}
                    <span
                      className={cn(
                        "font-semibold",
                        insights.trends.trend_direction === "上升"
                          ? "text-green-600 dark:text-green-400"
                          : insights.trends.trend_direction === "下降"
                          ? "text-red-600 dark:text-red-400"
                          : "text-gray-600 dark:text-gray-400"
                      )}
                    >
                      {insights.trends.trend_direction}
                    </span>
                  </p>
                )}
                {insights.trends?.total_growth_rate !== undefined && (
                  <p className="text-gray-700 dark:text-gray-300">
                    总体变化:{" "}
                    <span
                      className={cn(
                        "font-semibold",
                        insights.trends.total_growth_rate > 0
                          ? "text-green-600 dark:text-green-400"
                          : insights.trends.total_growth_rate < 0
                          ? "text-red-600 dark:text-red-400"
                          : "text-gray-600 dark:text-gray-400"
                      )}
                    >
                      {insights.trends.total_growth_rate > 0 ? "+" : ""}
                      {insights.trends.total_growth_rate.toFixed(2)}%
                    </span>
                  </p>
                )}
              </div>
            </div>
          )}

          {/* 异常检测 */}
          {hasAnomalies && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-orange-200 dark:border-orange-700">
              <h4 className="font-medium text-sm text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-orange-600 dark:text-orange-400" />
                异常检测
              </h4>
              <ul className="space-y-2 text-sm">
                {insights.anomalies?.slice(0, 3).map((anomaly, index) => (
                  <li
                    key={index}
                    className="text-gray-700 dark:text-gray-300 flex items-start gap-2"
                  >
                    <span className="text-orange-600 dark:text-orange-400">
                      •
                    </span>
                    <span>
                      {anomaly.description ||
                        `${anomaly.column}: ${anomaly.type}`}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 业务建议 */}
          {hasRecommendations && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-blue-200 dark:border-blue-700">
              <h4 className="font-medium text-sm text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                业务建议
              </h4>
              <ul className="space-y-2 text-sm">
                {insights.recommendations?.slice(0, 5).map((rec, index) => (
                  <li
                    key={index}
                    className="text-gray-700 dark:text-gray-300 flex items-start gap-2"
                  >
                    <span className="text-blue-600 dark:text-blue-400 font-bold">
                      {index + 1}.
                    </span>
                    <div>
                      {rec.type && (
                        <span className="inline-block px-2 py-0.5 rounded text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 mr-2">
                          {rec.type}
                        </span>
                      )}
                      <span>{typeof rec === 'string' ? rec : rec.content || JSON.stringify(rec)}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
