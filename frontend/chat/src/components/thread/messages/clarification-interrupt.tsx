/**
 * ClarificationInterruptView 组件
 * 简洁的澄清确认卡片，显示问题和选项
 */
import { useState } from "react";
import { useStreamContext } from "@/providers/Stream";
import { cn } from "@/lib/utils";
import { LoaderCircle, X } from "lucide-react";

export interface ClarificationQuestion {
  id: string;
  question: string;
  type: "choice" | "text";
  options?: string[];
  related_ambiguity?: string;
  recommended_option?: string;
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
  default_value?: string;
}

interface ClarificationInterruptViewProps {
  interrupt: ClarificationInterruptData;
}

export function ClarificationInterruptView({
  interrupt,
}: ClarificationInterruptViewProps) {
  const stream = useStreamContext();
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [customInput, setCustomInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showCustomInput, setShowCustomInput] = useState(false);

  const question = interrupt.questions?.[0];
  const options = question?.options || [];

  const handleSelect = (option: string) => {
    setSelectedOption(option);
    setShowCustomInput(false);
    // 直接提交选中的选项
    submitAnswer(option);
  };

  const handleCustomClick = () => {
    setShowCustomInput(true);
    setSelectedOption(null);
  };

  const handleCustomSubmit = () => {
    if (customInput.trim()) {
      submitAnswer(customInput.trim());
    }
  };

  const submitAnswer = async (answer: string) => {
    setIsSubmitting(true);
    
    const formattedResponses = {
      session_id: interrupt.session_id,
      answers: [{
        question_id: question?.id || "q_default",
        answer: answer,
      }],
    };

    try {
      stream.submit(
        {},
        {
          command: { resume: formattedResponses },
          streamMode: ["values", "custom"],
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
        command: { 
          resume: { 
            skipped: true,
            session_id: interrupt.session_id,
            original_query: interrupt.original_query 
          } 
        },
        streamMode: ["values", "custom"],
        streamSubgraphs: true,
      } as any
    );
  };

  if (!question) return null;

  return (
    <div className="w-full max-w-xl my-3">
      <div className="rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 shadow-sm overflow-hidden">
        {/* 问题 + 关闭按钮 */}
        <div className="px-4 py-3 flex items-start justify-between gap-3">
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {question.question}
          </p>
          <button
            onClick={handleSkip}
            className="flex-shrink-0 p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:text-slate-300 dark:hover:bg-zinc-800 transition-colors"
            title="跳过"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 选项按钮 */}
        <div className="px-4 pb-4 flex flex-wrap gap-2">
          {options.map((option) => (
            <button
              key={option}
              onClick={() => handleSelect(option)}
              disabled={isSubmitting}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm border transition-all",
                selectedOption === option
                  ? "bg-indigo-600 text-white border-indigo-600"
                  : "bg-slate-50 text-slate-600 border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-600 dark:bg-zinc-800 dark:text-slate-300 dark:border-zinc-700 dark:hover:border-indigo-500 dark:hover:text-indigo-400",
                isSubmitting && "opacity-50 cursor-not-allowed"
              )}
            >
              {isSubmitting && selectedOption === option ? (
                <LoaderCircle className="w-4 h-4 animate-spin inline mr-1" />
              ) : null}
              {option}
            </button>
          ))}
          
          {/* 其他选项 */}
          {showCustomInput ? (
            <div className="flex items-center gap-2 flex-1 min-w-[200px]">
              <input
                type="text"
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCustomSubmit()}
                placeholder="输入自定义值..."
                autoFocus
                className="flex-1 px-3 py-1.5 rounded-lg text-sm border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-slate-700 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:border-indigo-500"
              />
              <button
                onClick={handleCustomSubmit}
                disabled={!customInput.trim() || isSubmitting}
                className="px-3 py-1.5 rounded-lg text-sm bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                确定
              </button>
            </div>
          ) : (
            <button
              onClick={handleCustomClick}
              disabled={isSubmitting}
              className="px-3 py-1.5 rounded-lg text-sm border border-dashed border-slate-300 text-slate-500 hover:border-indigo-300 hover:text-indigo-600 dark:border-zinc-600 dark:text-slate-400 dark:hover:border-indigo-500 dark:hover:text-indigo-400 transition-colors"
            >
              其他...
            </button>
          )}
        </div>
      </div>
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
  try {
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
  } catch (e) {
    console.warn("Failed to extract clarification data:", e);
    return null;
  }
  
  return null;
}

/**
 * 检查 interrupt 是否为澄清类型
 */
