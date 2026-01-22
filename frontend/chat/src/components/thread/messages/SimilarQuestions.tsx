/**
 * 相似问题推荐组件
 * 
 * 展示与当前查询相关的推荐问题，点击可快速发起新查询
 */
import { useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, Lightbulb, MessageCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SimilarQuestionsEvent } from "@/types/stream-events";

interface SimilarQuestionsProps {
  data: SimilarQuestionsEvent;
  onSelect?: (question: string) => void;
}

export function SimilarQuestions({ data, onSelect }: SimilarQuestionsProps) {
  const [expanded, setExpanded] = useState(false);

  const questions = data?.questions || [];

  if (questions.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      {/* 头部 - 可点击展开/收起 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
      >
        <Lightbulb className="h-4 w-4 text-amber-500 flex-shrink-0" />
        <span className="font-medium text-slate-700 dark:text-slate-200">推荐相似问题</span>
        <span className="text-muted-foreground text-sm">({questions.length})</span>
        <div className="ml-auto">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-slate-400" />
          )}
        </div>
      </button>

      {/* 展开的问题列表 */}
      {expanded && (
        <div className="border-t border-slate-100 dark:border-slate-800">
          <div className="p-4 space-y-2">
            {questions.map((question, index) => (
              <button
                key={index}
                onClick={() => onSelect?.(question)}
                className={cn(
                  "flex items-start gap-2 w-full text-left p-3 rounded-md",
                  "bg-slate-50 dark:bg-slate-800 hover:bg-blue-50 dark:hover:bg-blue-900/30",
                  "text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400",
                  "transition-colors group"
                )}
              >
                <MessageCircle className="h-4 w-4 mt-0.5 flex-shrink-0 text-slate-400 group-hover:text-blue-500" />
                <span className="text-sm leading-relaxed">{question}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
