/**
 * ClarificationCard 组件
 * 用于展示澄清问题并收集用户回复
 */
import { useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Label } from "./ui/label";
import { Input } from "./ui/input";
import { cn } from "@/lib/utils";
import { HelpCircle, Send } from "lucide-react";

export interface ClarificationQuestion {
  id: string;
  question: string;
  type: "choice" | "text";
  options?: string[];
  related_ambiguity?: string;
}

export interface ClarificationResponse {
  question_id: string;
  answer: string;
}

interface ClarificationCardProps {
  questions: ClarificationQuestion[];
  onSubmit: (responses: ClarificationResponse[]) => void;
  className?: string;
}

export function ClarificationCard({
  questions,
  onSubmit,
  className,
}: ClarificationCardProps) {
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

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
      alert("请回答所有问题");
      return;
    }

    setIsSubmitting(true);
    const formattedResponses: ClarificationResponse[] = questions.map((q) => ({
      question_id: q.id,
      answer: responses[q.id],
    }));

    try {
      await onSubmit(formattedResponses);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card
      className={cn(
        "p-4 mb-4 border-blue-200 bg-blue-50 dark:bg-blue-950 dark:border-blue-800",
        className
      )}
    >
      <div className="flex items-start gap-3 mb-4">
        <HelpCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" />
        <div className="flex-1">
          <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-1">
            需要澄清一些信息
          </h3>
          <p className="text-sm text-blue-700 dark:text-blue-300">
            为了更准确地理解您的需求，请回答以下问题：
          </p>
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
                className="w-full"
              />
            )}

            {question.related_ambiguity && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                相关问题: {question.related_ambiguity}
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 flex justify-end">
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

// LoaderCircle icon (if not available)
function LoaderCircle({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}
