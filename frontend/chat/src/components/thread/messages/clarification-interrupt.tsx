/**
 * ClarificationInterruptView 组件
 * 处理澄清类型的 interrupt，显示澄清问题并收集用户回复
 * 
 * 美化版本 (2026-01-22)
 */
import { useState } from "react";
import { useStreamContext } from "@/providers/Stream";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { 
  MessageCircleQuestion, 
  Send, 
  LoaderCircle, 
  SkipForward,
  CheckCircle2,
  Lightbulb,
  ChevronRight
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export interface ClarificationQuestion {
  id: string;
  question: string;
  type: "choice" | "text";
  options?: string[];
  related_ambiguity?: string;
}

export interface ClarificationInterruptData {
  type: "clarification" | "clarification_request";
  questions: ClarificationQuestion[];
  reason?: string;
  message?: string;
  round?: number;
  max_rounds?: number;
  session_id?: string;
  original_query?: string;
  related_ambiguity?: string;
}

interface ClarificationInterruptViewProps {
  interrupt: ClarificationInterruptData;
}

export function ClarificationInterruptView({
  interrupt,
}: ClarificationInterruptViewProps) {
  const stream = useStreamContext();
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);

  const questions = interrupt.questions || [];
  const totalQuestions = questions.length;
  const currentQuestion = questions[currentQuestionIndex];
  const allAnswered = questions.every((q) => responses[q.id]?.trim());
  const currentAnswered = currentQuestion ? !!responses[currentQuestion.id]?.trim() : false;

  const handleChoiceSelect = (questionId: string, answer: string) => {
    setResponses((prev) => ({
      ...prev,
      [questionId]: answer,
    }));
    // 自动跳转到下一题（如果有）
    if (currentQuestionIndex < totalQuestions - 1) {
      setTimeout(() => setCurrentQuestionIndex((prev) => prev + 1), 300);
    }
  };

  const handleTextChange = (questionId: string, answer: string) => {
    setResponses((prev) => ({
      ...prev,
      [questionId]: answer,
    }));
  };

  const handleSubmit = async () => {
    if (!allAnswered) return;

    setIsSubmitting(true);

    const formattedResponses = {
      session_id: interrupt.session_id,
      answers: questions.map((q) => ({
        question_id: q.id,
        answer: responses[q.id],
      })),
    };

    try {
      stream.submit(
        {},
        {
          command: { resume: formattedResponses },
          streamMode: ["values", "messages"],
          streamSubgraphs: true,
        } as any
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = () => {
    stream.submit(
      {},
      {
        command: { resume: [] },
        streamMode: ["values", "messages"],
        streamSubgraphs: true,
      } as any
    );
  };

  const goToQuestion = (index: number) => {
    setCurrentQuestionIndex(index);
  };

  return (
    <div className="w-full max-w-xl">
      {/* 主卡片 - 精简版 */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="rounded-xl overflow-hidden bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 shadow-sm"
      >
        {/* 紧凑头部 */}
        <div className="px-4 py-3 bg-gradient-to-r from-blue-500 to-indigo-500 dark:from-blue-600 dark:to-indigo-600">
          <div className="flex items-center gap-2">
            <MessageCircleQuestion className="w-5 h-5 text-white flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {interrupt.original_query ? `关于「${interrupt.original_query}」需要补充信息` : "需要您补充一点信息"}
              </p>
            </div>
            {totalQuestions > 1 && (
              <span className="text-xs text-white/80 flex-shrink-0">
                {currentQuestionIndex + 1}/{totalQuestions}
              </span>
            )}
          </div>
        </div>

        {/* 原因提示 - 更紧凑 */}
        {interrupt.reason && (
          <div className="px-4 py-2 bg-amber-50/80 dark:bg-amber-900/20 border-b border-amber-100/50 dark:border-amber-800/20">
            <p className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
              <Lightbulb className="w-3 h-3 flex-shrink-0" />
              <span className="line-clamp-2">{interrupt.reason}</span>
            </p>
          </div>
        )}

        {/* 进度条 - 多问题时显示 */}
        {totalQuestions > 1 && (
          <div className="px-4 pt-3">
            <div className="flex gap-1">
              {questions.map((q, idx) => (
                <button
                  key={q.id}
                  onClick={() => goToQuestion(idx)}
                  className={cn(
                    "h-1 flex-1 rounded-full transition-all",
                    idx === currentQuestionIndex
                      ? "bg-blue-500"
                      : responses[q.id]?.trim()
                      ? "bg-green-400"
                      : "bg-gray-200 dark:bg-slate-600"
                  )}
                />
              ))}
            </div>
          </div>
        )}

        {/* 问题区域 - 紧凑 */}
        <div className="p-4">
          <AnimatePresence mode="wait">
            {currentQuestion && (
              <motion.div
                key={currentQuestion.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="space-y-3"
              >
                {/* 问题 */}
                <p className="text-sm font-medium text-gray-800 dark:text-gray-100">
                  {currentQuestion.question}
                </p>

                {/* 选项 */}
                {currentQuestion.type === "choice" && currentQuestion.options ? (
                  <div className="grid gap-1.5">
                    {currentQuestion.options.map((option) => (
                      <button
                        key={option}
                        onClick={() => handleChoiceSelect(currentQuestion.id, option)}
                        className={cn(
                          "w-full text-left px-3 py-2 rounded-lg text-sm transition-all",
                          responses[currentQuestion.id] === option
                            ? "bg-blue-500 text-white"
                            : "bg-gray-50 dark:bg-slate-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700"
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0",
                            responses[currentQuestion.id] === option
                              ? "border-white bg-white"
                              : "border-gray-300 dark:border-slate-500"
                          )}>
                            {responses[currentQuestion.id] === option && (
                              <CheckCircle2 className="w-3 h-3 text-blue-500" />
                            )}
                          </span>
                          {option}
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <Input
                    placeholder="请输入您的回答..."
                    value={responses[currentQuestion.id] || ""}
                    onChange={(e) => handleTextChange(currentQuestion.id, e.target.value)}
                    className="w-full h-9 text-sm rounded-lg"
                  />
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* 底部按钮 - 紧凑 */}
        <div className="px-4 py-3 bg-gray-50 dark:bg-slate-800/50 border-t border-gray-100 dark:border-slate-700 flex items-center justify-between gap-2">
          {totalQuestions > 1 && (
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCurrentQuestionIndex((prev) => Math.max(0, prev - 1))}
                disabled={currentQuestionIndex === 0}
                className="h-8 px-2 text-xs text-gray-500"
              >
                上一题
              </Button>
              {currentQuestionIndex < totalQuestions - 1 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentQuestionIndex((prev) => prev + 1)}
                  disabled={!currentAnswered}
                  className="h-8 px-2 text-xs text-blue-600"
                >
                  下一题
                  <ChevronRight className="w-3 h-3 ml-0.5" />
                </Button>
              )}
            </div>
          )}
          <div className={cn("flex gap-2", totalQuestions <= 1 && "w-full justify-between")}>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSkip}
              disabled={isSubmitting}
              className="h-8 text-xs text-gray-500"
            >
              跳过
            </Button>
            <Button
              size="sm"
              onClick={handleSubmit}
              disabled={isSubmitting || !allAnswered}
              className={cn(
                "h-8 px-4 text-xs rounded-lg",
                allAnswered
                  ? "bg-blue-500 hover:bg-blue-600 text-white"
                  : "bg-gray-200 dark:bg-slate-700 text-gray-400"
              )}
            >
              {isSubmitting ? (
                <LoaderCircle className="w-3 h-3 animate-spin" />
              ) : (
                <>
                  <Send className="w-3 h-3 mr-1" />
                  提交
                </>
              )}
            </Button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

/**
 * 从 interrupt 对象中提取澄清数据
 * 支持多种包装格式
 */
export function extractClarificationData(
  interrupt: unknown
): ClarificationInterruptData | null {
  if (!interrupt || typeof interrupt !== "object") return null;
  
  const obj = interrupt as Record<string, unknown>;
  
  // 直接格式
  if (
    (obj.type === "clarification" || obj.type === "clarification_request") &&
    Array.isArray(obj.questions)
  ) {
    return obj as ClarificationInterruptData;
  }
  
  // 包装在 value 中的格式
  if (obj.value && typeof obj.value === "object") {
    const valueObj = obj.value as Record<string, unknown>;
    if (
      (valueObj.type === "clarification" || valueObj.type === "clarification_request") &&
      Array.isArray(valueObj.questions)
    ) {
      return valueObj as ClarificationInterruptData;
    }
  }
  
  // 数组格式 (取第一个元素)
  if (Array.isArray(interrupt) && interrupt.length > 0) {
    const first = interrupt[0];
    if (first && typeof first === "object") {
      // 检查数组元素的 value 属性
      const firstValue = (first as Record<string, unknown>).value;
      if (firstValue && typeof firstValue === "object") {
        const valueObj = firstValue as Record<string, unknown>;
        if (
          (valueObj.type === "clarification" || valueObj.type === "clarification_request") &&
          Array.isArray(valueObj.questions)
        ) {
          return valueObj as ClarificationInterruptData;
        }
      }
    }
  }
  
  return null;
}

/**
 * 检查 interrupt 是否为澄清类型
 */
export function isClarificationInterrupt(
  interrupt: unknown
): boolean {
  return extractClarificationData(interrupt) !== null;
}
