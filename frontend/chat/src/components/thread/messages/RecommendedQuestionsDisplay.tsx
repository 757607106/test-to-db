/**
 * 推荐问题展示组件（独立于流水线，在回答后展示）
 * 
 * 显示推荐的问题，点击可直接发送
 */
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Lightbulb,
  MessageCircle,
  ChevronDown,
  ArrowRight,
} from "lucide-react";

interface RecommendedQuestionsDisplayProps {
  questions: string[];
  onSelect: (question: string) => void;
}

export function RecommendedQuestionsDisplay({ 
  questions, 
  onSelect 
}: RecommendedQuestionsDisplayProps) {
  // 默认展开
  const [isExpanded, setIsExpanded] = useState(true);

  if (!questions || questions.length === 0) return null;

  return (
    <div className="mt-4 rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50 via-purple-50/30 to-white overflow-hidden shadow-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-indigo-100/30 transition-colors"
      >
        <div className="p-2 rounded-lg bg-gradient-to-br from-indigo-100 to-purple-100 shadow-sm">
          <Lightbulb className="h-4 w-4 text-indigo-600" />
        </div>
        <div className="flex flex-col items-start">
          <span className="font-semibold text-sm text-indigo-800">继续探索</span>
          <span className="text-xs text-indigo-500">猜你想问</span>
        </div>
        <span className="text-xs text-white px-2.5 py-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full font-medium shadow-sm">
          {questions.length} 个推荐
        </span>
        <motion.div
          animate={{ rotate: isExpanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="ml-auto"
        >
          <ChevronDown className="h-4 w-4 text-indigo-500" />
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
            <div className="px-4 pb-4 grid gap-2">
              {questions.map((q, i) => (
                <motion.button
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  onClick={() => onSelect(q)}
                  className="group flex items-start gap-3 w-full text-left p-3.5 rounded-xl bg-white border border-indigo-100 text-sm text-slate-700 hover:border-indigo-300 hover:bg-gradient-to-r hover:from-indigo-50 hover:to-purple-50 hover:shadow-md hover:scale-[1.01] transition-all duration-200"
                >
                  <div className="p-1.5 rounded-lg bg-indigo-50 group-hover:bg-indigo-100 transition-colors flex-shrink-0">
                    <MessageCircle className="h-3.5 w-3.5 text-indigo-500 group-hover:text-indigo-600" />
                  </div>
                  <span className="leading-relaxed group-hover:text-indigo-800 flex-1">{q}</span>
                  <ArrowRight className="h-4 w-4 flex-shrink-0 text-slate-300 group-hover:text-indigo-500 transition-colors" />
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
