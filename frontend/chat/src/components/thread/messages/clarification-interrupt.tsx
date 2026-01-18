/**
 * ClarificationInterruptView 组件
 * 处理澄清类型的 interrupt，显示澄清问题并收集用户回复
 */
import { useState } from "react";
import { useStreamContext } from "@/providers/Stream";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { HelpCircle, Send, LoaderCircle } from "lucide-react";

export interface ClarificationQuestion {
  id: string;
  question: string;
  type: "choice" | "text";
  options?: string[];
}

export interface ClarificationInterruptData {
  type: "clarification";
  questions: ClarificationQuestion[];
  reason?: string;
  message?: string;
  round?: number;
  max_rounds?: number;
  session_id?: string;  // 用于验证 resume 数据是否匹配当前查询
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

  const questions = interrupt.questions || [];

  const handleChoiceSelect = (questionId: string, answer: string) => {
    setResponses((prev) => ({
      ...prev,
      [questionId]: answer,
    }));
  };

  const handleTextChange = (questionId: string, answer: string) => {
    setResponses((prev) => ({
      ...prev,
      [questionId]: answer,
    }));
  };

  const handleSubmit = async () => {
    // 验证所有问题都已回答
    const allAnswered = questions.every((q) => responses[q.id]?.trim());
    if (!allAnswered) {
      return;
    }

    setIsSubmitting(true);

    // 格式化响应，包含 session_id 用于验证
    const formattedResponses = {
      session_id: interrupt.session_id,  // 包含 session_id 用于后端验证
      answers: questions.map((q) => ({
        question_id: q.id,
        answer: responses[q.id],
      })),
    };

    try {
      // 使用 command.resume 恢复图执行（正确方式）
      stream.submit(
        {},  // 第一个参数为空对象
        {
          command: {
            resume: formattedResponses,  // resume 放在 command 对象中
          },
          streamMode: ["values", "messages"],
          streamSubgraphs: true,
        } as any
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = () => {
    // 跳过澄清，直接继续
    stream.submit(
      {},  // 第一个参数为空对象
      {
        command: {
          resume: [],  // resume 放在 command 对象中
        },
        streamMode: ["values", "messages"],
        streamSubgraphs: true,
      } as any
    );
  };

  return (
    <Card className="p-4 mb-4 border-blue-200 bg-blue-50 dark:bg-blue-950 dark:border-blue-800">
      <div className="flex items-start gap-3 mb-4">
        <HelpCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-1">
            需要澄清一些信息
          </h3>
          <p className="text-sm text-blue-700 dark:text-blue-300">
            {interrupt.message || "为了更准确地理解您的需求，请回答以下问题："}
          </p>
          {interrupt.reason && (
            <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
              原因: {interrupt.reason}
            </p>
          )}
          {interrupt.round && interrupt.max_rounds && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              澄清轮次: {interrupt.round}/{interrupt.max_rounds}
            </p>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {questions.map((question, index) => (
          <div key={question.id} className="space-y-2">
            <Label className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {index + 1}. {question.question}
            </Label>

            {question.type === "choice" && question.options ? (
              <div className="space-y-2">
                {question.options.map((option) => (
                  <button
                    key={option}
                    onClick={() => handleChoiceSelect(question.id, option)}
                    className={cn(
                      "w-full text-left px-4 py-2 rounded-md border transition-colors",
                      responses[question.id] === option
                        ? "border-blue-600 bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-100"
                        : "border-gray-300 dark:border-gray-600 hover:border-blue-400 bg-white dark:bg-gray-800"
                    )}
                  >
                    {option}
                  </button>
                ))}
              </div>
            ) : (
              <Input
                placeholder="请输入您的回答..."
                value={responses[question.id] || ""}
                onChange={(e) => handleTextChange(question.id, e.target.value)}
                className="w-full bg-white dark:bg-gray-800"
              />
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 flex justify-end gap-2">
        <Button
          variant="outline"
          onClick={handleSkip}
          disabled={isSubmitting}
        >
          跳过
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={
            isSubmitting ||
            !questions.every((q) => responses[q.id]?.trim())
          }
          className="gap-2"
        >
          {isSubmitting ? (
            <>
              <LoaderCircle className="w-4 h-4 animate-spin" />
              提交中...
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              提交回答
            </>
          )}
        </Button>
      </div>
    </Card>
  );
}

/**
 * 检查 interrupt 是否为澄清类型
 */
export function isClarificationInterrupt(
  interrupt: unknown
): interrupt is ClarificationInterruptData {
  if (!interrupt || typeof interrupt !== "object") return false;
  const obj = interrupt as Record<string, unknown>;
  return obj.type === "clarification" && Array.isArray(obj.questions);
}
