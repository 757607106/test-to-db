/**
 * ClarificationInterruptView 组件
 * 处理澄清类型的 interrupt，显示澄清问题并收集用户回复
 * 
 * 问卷式多选设计 (2026-01-23)
 * - 选项使用字母标记 (A/B/C/D)
 * - 最后一个选项为自定义输入
 * - 支持"推荐选项"提示
 * - 2026-01-24: UI 重构，适配亮/暗色模式，移除硬编码深色背景
 */
import { useState, useMemo } from "react";
import { useStreamContext } from "@/providers/Stream";
import { cn } from "@/lib/utils";
import { 
  MessageCircleQuestion, 
  LoaderCircle, 
  Sparkles,
  Check
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
    <div className="w-full max-w-2xl my-4">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="rounded-2xl overflow-hidden bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-xl"
      >
        {/* 头部标题 */}
        <div className="px-6 py-4 border-b border-slate-100 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400 rounded-lg">
              <MessageCircleQuestion className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">需要您的确认</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">为了准确执行，请帮忙澄清以下细节</p>
            </div>
          </div>
        </div>

        {/* 问题列表 */}
        <div className="px-6 py-6 space-y-8">
          <AnimatePresence mode="wait">
            {questions.map((question, qIndex) => (
              <motion.div
                key={question.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2, delay: qIndex * 0.1 }}
                className="space-y-4"
              >
                {/* 问题标题 */}
                <div className="flex gap-3">
                   <span className="flex items-center justify-center w-6 h-6 rounded-full bg-slate-100 dark:bg-zinc-800 text-xs font-bold text-slate-500 dark:text-slate-400 flex-shrink-0 mt-0.5">
                     {qIndex + 1}
                   </span>
                   <p className="text-sm font-medium text-slate-800 dark:text-slate-200 leading-relaxed">
                     {question.question}
                   </p>
                </div>

                {/* 选项列表 */}
                <div className="pl-9 space-y-2.5">
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
                              "group w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all border shadow-sm",
                              isSelected
                                ? "bg-indigo-50 border-indigo-200 shadow-indigo-100 dark:bg-indigo-900/20 dark:border-indigo-800 dark:shadow-none"
                                : "bg-white border-slate-200 hover:border-indigo-200 hover:shadow-md dark:bg-zinc-800/50 dark:border-zinc-700 dark:hover:bg-zinc-800 dark:hover:border-zinc-600"
                            )}
                          >
                            <span className={cn(
                              "flex items-center justify-center w-6 h-6 rounded-md text-xs font-bold flex-shrink-0 transition-colors",
                              isSelected
                                ? "bg-indigo-600 text-white"
                                : "bg-slate-100 text-slate-500 group-hover:bg-indigo-50 group-hover:text-indigo-600 dark:bg-zinc-700 dark:text-zinc-400 dark:group-hover:bg-zinc-600"
                            )}>
                              {isSelected ? <Check className="w-3.5 h-3.5" /> : letter}
                            </span>
                            <span className={cn(
                              "text-sm flex-1 transition-colors",
                              isSelected 
                                ? "text-indigo-900 font-medium dark:text-indigo-100" 
                                : "text-slate-600 group-hover:text-slate-900 dark:text-slate-300 dark:group-hover:text-slate-100"
                            )}>
                              {option}
                              {isRecommended && (
                                <span className="ml-2 inline-flex items-center gap-1 text-xs font-normal text-amber-500 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 px-2 py-0.5 rounded-full border border-amber-100 dark:border-amber-800/50">
                                  <Sparkles className="w-3 h-3" /> 推荐
                                </span>
                              )}
                            </span>
                          </button>
                        );
                      })}
                      
                      {/* 自定义输入选项 */}
                      <div className="relative">
                        <button
                          onClick={() => handleOptionSelect(question.id, "", true)}
                          className={cn(
                            "group w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all border shadow-sm",
                            responses[question.id] === "__custom__"
                              ? "bg-indigo-50 border-indigo-200 dark:bg-indigo-900/20 dark:border-indigo-800"
                              : "bg-white border-slate-200 hover:border-indigo-200 hover:shadow-md dark:bg-zinc-800/50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                          )}
                        >
                          <span className={cn(
                            "flex items-center justify-center w-6 h-6 rounded-md text-xs font-bold flex-shrink-0 transition-colors",
                            responses[question.id] === "__custom__"
                              ? "bg-indigo-600 text-white"
                              : "bg-slate-100 text-slate-500 group-hover:bg-indigo-50 group-hover:text-indigo-600 dark:bg-zinc-700 dark:text-zinc-400"
                          )}>
                            {responses[question.id] === "__custom__" ? <Check className="w-3.5 h-3.5" /> : (OPTION_LETTERS[question.options.length] || "E")}
                          </span>
                          
                          {responses[question.id] === "__custom__" ? (
                            <input
                              type="text"
                              value={customInputs[question.id] || ""}
                              onChange={(e) => handleCustomInputChange(question.id, e.target.value)}
                              onClick={(e) => e.stopPropagation()}
                              placeholder="请输入您的具体需求..."
                              autoFocus
                              className="flex-1 bg-transparent text-sm text-indigo-900 dark:text-indigo-100 placeholder-indigo-300 outline-none"
                            />
                          ) : (
                            <span className="text-sm text-slate-500 dark:text-slate-400">其他 (自定义输入)</span>
                          )}
                        </button>
                      </div>
                    </>
                  ) : (
                    /* 纯文本输入类型 */
                    <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:border-indigo-500 transition-all shadow-sm">
                      <span className="flex items-center justify-center w-6 h-6 rounded-md bg-slate-100 dark:bg-zinc-700 text-xs font-bold text-slate-500 dark:text-slate-400 flex-shrink-0">
                        A
                      </span>
                      <input
                        type="text"
                        value={responses[question.id] || ""}
                        onChange={(e) => setResponses(prev => ({ ...prev, [question.id]: e.target.value }))}
                        placeholder="请输入您的回答..."
                        className="flex-1 bg-transparent text-sm text-slate-800 dark:text-slate-200 placeholder-slate-400 outline-none"
                      />
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* 底部操作栏 */}
        <div className="px-6 py-4 border-t border-slate-100 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-900/50 flex items-center justify-end gap-3">
            <button
              onClick={handleCancel}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-200/50 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-zinc-800 rounded-lg transition-colors"
            >
              跳过/取消
            </button>
            <button
              onClick={handleSubmit}
              disabled={isSubmitting || !allAnswered}
              className={cn(
                "px-6 py-2 rounded-lg text-sm font-medium transition-all shadow-sm flex items-center gap-2",
                allAnswered && !isSubmitting
                  ? "bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-indigo-200 dark:hover:shadow-none"
                  : "bg-slate-200 text-slate-400 cursor-not-allowed dark:bg-zinc-800 dark:text-zinc-600"
              )}
            >
              {isSubmitting ? (
                <>
                  <LoaderCircle className="w-4 h-4 animate-spin" />
                  提交中...
                </>
              ) : (
                "确认提交"
              )}
            </button>
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
