/**
 * 数据分析展示组件（在图表下方显示）
 * 
 * 展示从 SQL 查询中提取的数据分析结果
 */
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Lightbulb, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SQLStepEvent } from "@/types/stream-events";

interface DataAnalysisDisplayProps {
  analysisStep?: SQLStepEvent;
}

export function DataAnalysisDisplay({ analysisStep }: DataAnalysisDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  // 如果没有分析数据或状态不是 completed，则不显示
  if (!analysisStep || analysisStep.status !== "completed" || !analysisStep.result) {
    return null;
  }

  return (
    <div className="mt-4 rounded-xl border border-emerald-200 bg-gradient-to-b from-emerald-50/50 to-white overflow-hidden shadow-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-emerald-50/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-emerald-100 to-teal-100 shadow-sm">
            <Lightbulb className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="flex flex-col items-start">
            <span className="font-semibold text-sm text-emerald-800">数据分析</span>
            <span className="text-xs text-emerald-500">AI 生成的洞察</span>
          </div>
        </div>

        <motion.div
          animate={{ rotate: isExpanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="h-4 w-4 text-emerald-500" />
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
            <div className="p-4">
              <div className="bg-white rounded-lg border border-emerald-200 p-4">
                <div className="prose prose-sm max-w-none text-slate-700 whitespace-pre-wrap">
                  {analysisStep.result}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
