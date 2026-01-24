/**
 * ClarificationInterruptView 组件
 * 处理澄清类型的 interrupt，显示澄清问题并收集用户回复
 * 
 * 问卷式多选设计 (2026-01-23)
 * - 选项使用字母标记 (A/B/C/D)
 * - 最后一个选项为自定义输入
 * - 支持"推荐选项"提示
 */
import { useState, useMemo } from "react";
import { useStreamContext } from "@/providers/Stream";
import { cn } from "@/lib/utils";
import { 
  MessageCircleQuestion, 
  LoaderCircle, 
  Sparkles,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export interface ClarificationQuestion {
  id: string;
  question: string;
  type: "choice" | "text";
  options?: string[];
  related_ambiguity?: string;
  recommended_option?: string; // 推荐选项
}

export interface ClarificationInterruptData {
  type: "clarification" | "clarification_request" | "schema_clarification";
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

// 选项字母标记
const OPTION_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"];

export function ClarificationInterruptView({
  interrupt,
}: ClarificationInterruptViewProps) {
  const stream = useStreamContext();
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [customInputs, setCustomInputs] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const questions = interrupt.questions || [];
  
  // 计算是否全部回答完成
  const allAnswered = useMemo(() => {
    return questions.every((q) => {
      const response = responses[q.id];
      if (!response) return false;
      // 如果选择了"其他"选项，需要检查自定义输入是否有值
      if (response === "__custom__") {
        return !!customInputs[q.id]?.trim();
      }
      return true;
    });
  }, [questions, responses, customInputs]);

  const handleOptionSelect = (questionId: string, option: string, isCustom: boolean = false) => {
    setResponses((prev) => ({
      ...prev,
      [questionId]: isCustom ? "__custom__" : option,
    }));
  };

  const handleCustomInputChange = (questionId: string, value: string) => {
    setCustomInputs((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  const handleSubmit = async () => {
    if (!allAnswered) return;

    setIsSubmitting(true);

    const formattedResponses = {
      session_id: interrupt.session_id,
      answers: questions.map((q) => ({
        question_id: q.id,
        answer: responses[q.id] === "__custom__" 
          ? customInputs[q.id] 
          : responses[q.id],
      })),
    };

    try {
      stream.submit(
        {},
        {
          command: { resume: formattedResponses },
          streamMode: ["values"],
          streamSubgraphs: true,
        } as any
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    stream.submit(
      {},
      {
        command: { 
          resume: { 
            skipped: true,
            session_id: interrupt.session_id,
            original_query: interrupt.original_query 
          } 
        },
        streamMode: ["values"],
        streamSubgraphs: true,
      } as any
    );
  };

  return (
    <div className="w-full max-w-2xl">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="rounded-2xl overflow-hidden bg-[#2A2A2E] dark:bg-[#1C1C1E] border border-white/10 shadow-xl"
      >
        {/* 头部标题 */}
        <div className="px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <MessageCircleQuestion className="w-5 h-5 text-slate-400" />
            <span className="text-base font-medium text-slate-200">请回答以下问题</span>
          </div>
        </div>

        {/* 问题列表 */}
        <div className="px-6 py-5 space-y-6">
          <AnimatePresence mode="wait">
            {questions.map((question, qIndex) => (
              <motion.div
                key={question.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15, delay: qIndex * 0.05 }}
                className="space-y-3"
              >
                {/* 问题标题 */}
                <p className="text-sm font-semibold text-white">
                  {qIndex + 1}. {question.question}
                </p>

                {/* 选项列表 */}
                <div className="space-y-2">
                  {question.type === "choice" && question.options ? (
                    <>
                      {question.options.map((option, optIndex) => {
                        const letter = OPTION_LETTERS[optIndex] || String(optIndex + 1);
                        const isSelected = responses[question.id] === option;
                        const isRecommended = question.recommended_option === option;
                        
                        return (
                          <button
                            key={option}
                            onClick={() => handleOptionSelect(question.id, option)}
                            className={cn(
                              "w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all",
                              isSelected
                                ? "bg-blue-600/20 border border-blue-500/50"
                                : "bg-white/5 border border-transparent hover:bg-white/10"
                            )}
                          >
                            <span className={cn(
                              "flex items-center justify-center w-7 h-7 rounded-lg text-sm font-medium flex-shrink-0",
                              isSelected
                                ? "bg-blue-600 text-white"
                                : "bg-white/10 text-slate-400"
                            )}>
                              {letter}
                            </span>
                            <span className={cn(
                              "text-sm flex-1",
                              isSelected ? "text-white" : "text-slate-400"
                            )}>
                              {option}
                              {isRecommended && (
                                <span className="ml-2 text-xs text-blue-400">(推荐)</span>
                              )}
                            </span>
                          </button>
                        );
                      })}
                      
                      {/* 自定义输入选项 - 始终作为最后一个选项 */}
                      <div className="space-y-2">
                        <button
                          onClick={() => handleOptionSelect(question.id, "", true)}
                          className={cn(
                            "w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all",
                            responses[question.id] === "__custom__"
                              ? "bg-blue-600/20 border border-blue-500/50"
                              : "bg-white/5 border border-transparent hover:bg-white/10"
                          )}
                        >
                          <span className={cn(
                            "flex items-center justify-center w-7 h-7 rounded-lg text-sm font-medium flex-shrink-0",
                            responses[question.id] === "__custom__"
                              ? "bg-blue-600 text-white"
                              : "bg-white/10 text-slate-400"
                          )}>
                            {OPTION_LETTERS[question.options.length] || "E"}
                          </span>
                          {responses[question.id] === "__custom__" ? (
                            <input
                              type="text"
                              value={customInputs[question.id] || ""}
                              onChange={(e) => handleCustomInputChange(question.id, e.target.value)}
                              onClick={(e) => e.stopPropagation()}
                              placeholder="请输入您的答案..."
                              autoFocus
                              className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 outline-none"
                            />
                          ) : (
                            <span className="text-sm text-slate-500">其他 (自定义输入)</span>
                          )}
                        </button>
                      </div>
                    </>
                  ) : (
                    /* 纯文本输入类型 */
                    <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white/5 border border-white/10">
                      <span className="flex items-center justify-center w-7 h-7 rounded-lg text-sm font-medium bg-white/10 text-slate-400 flex-shrink-0">
                        A
                      </span>
                      <input
                        type="text"
                        value={responses[question.id] || ""}
                        onChange={(e) => setResponses(prev => ({ ...prev, [question.id]: e.target.value }))}
                        placeholder="请输入您的答案..."
                        className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 outline-none"
                      />
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* 底部操作栏 */}
        <div className="px-6 py-4 border-t border-white/10 flex items-center justify-between">
          {/* 推荐选项提示 */}
          <div className="flex items-center gap-2 text-slate-500">
            <Sparkles className="w-4 h-4" />
            <span className="text-sm">推荐选项</span>
          </div>

          {/* 按钮组 */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleCancel}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm text-slate-400 hover:text-slate-300 transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSubmit}
              disabled={isSubmitting || !allAnswered}
              className={cn(
                "px-5 py-2 rounded-lg text-sm font-medium transition-all",
                allAnswered && !isSubmitting
                  ? "bg-blue-600 text-white hover:bg-blue-500"
                  : "bg-white/10 text-slate-500 cursor-not-allowed"
              )}
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <LoaderCircle className="w-4 h-4 animate-spin" />
                  提交中...
                </span>
              ) : (
                "提交"
              )}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

/**
 * 从 interrupt 对象中提取澄清数据
 * 支持多种包装格式
 * 
 * 修复 (2026-01-23): 增加对嵌套 interrupt 格式的支持
 */
export function extractClarificationData(
  interrupt: unknown
): ClarificationInterruptData | null {
  if (!interrupt || typeof interrupt !== "object") return null;
  
  const obj = interrupt as Record<string, unknown>;
  
  // 直接格式
  if (
    (obj.type === "clarification" || obj.type === "clarification_request" || obj.type === "schema_clarification") &&
    Array.isArray(obj.questions)
  ) {
    return obj as unknown as ClarificationInterruptData;
  }
  
  // 包装在 value 中的格式
  if (obj.value && typeof obj.value === "object") {
    const valueObj = obj.value as Record<string, unknown>;
    if (
      (valueObj.type === "clarification" || valueObj.type === "clarification_request" || valueObj.type === "schema_clarification") &&
      Array.isArray(valueObj.questions)
    ) {
      return valueObj as unknown as ClarificationInterruptData;
    }
  }
  
  // 嵌套 interrupt 格式 (LangGraph 某些版本可能使用)
  if (obj.interrupt && typeof obj.interrupt === "object") {
    return extractClarificationData(obj.interrupt);
  }
  
  // 数组格式 (取第一个元素)
  if (Array.isArray(interrupt) && interrupt.length > 0) {
    const first = interrupt[0];
    if (first && typeof first === "object") {
      // 直接检查数组元素
      const firstObj = first as Record<string, unknown>;
      if (
        (firstObj.type === "clarification" || firstObj.type === "clarification_request" || firstObj.type === "schema_clarification") &&
        Array.isArray(firstObj.questions)
      ) {
        return firstObj as unknown as ClarificationInterruptData;
      }
      
      // 检查数组元素的 value 属性
      const firstValue = firstObj.value;
      if (firstValue && typeof firstValue === "object") {
        const valueObj = firstValue as Record<string, unknown>;
        if (
          (valueObj.type === "clarification" || valueObj.type === "clarification_request" || valueObj.type === "schema_clarification") &&
          Array.isArray(valueObj.questions)
        ) {
          return valueObj as unknown as ClarificationInterruptData;
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
