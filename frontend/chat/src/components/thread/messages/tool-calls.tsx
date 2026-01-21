/**
 * 工具调用组件
 * 
 * 基于官方 agent-chat-ui 实现，纯文字风格，紧凑排版
 * @see https://github.com/langchain-ai/agent-chat-ui
 */
import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * 检查是否为复杂值（数组或对象）
 */
function isComplexValue(value: any): boolean {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

/**
 * 工具名称映射 - 将英文工具名转换为友好显示
 */
const toolNameMap: Record<string, string> = {
  transfer_to_schema_agent: "模式分析",
  transfer_to_sql_generator_agent: "SQL生成",
  transfer_to_sql_executor_agent: "SQL执行",
  transfer_to_chart_generator_agent: "图表生成",
  transfer_to_clarification_agent: "澄清问题",
  transfer_to_error_recovery_agent: "错误恢复",
  analyze_user_query: "查询分析",
  generate_sql: "SQL生成",
  execute_sql: "SQL执行",
  generate_chart: "图表生成",
};

/**
 * 单个工具调用卡片组件 - 紧凑纯文字风格
 */
function ToolCallCard({ 
  toolCall, 
  status = "running",
  index 
}: { 
  toolCall: NonNullable<AIMessage["tool_calls"]>[number];
  status?: "running" | "complete" | "error";
  index: number;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const args = (toolCall.args || {}) as Record<string, any>;
  const hasArgs = Object.keys(args).length > 0;
  
  // 获取工具显示名称
  const toolLabel = toolNameMap[toolCall.name || ""] || toolCall.name || "工具调用";

  // 状态文字和样式
  const statusConfig = {
    running: { text: "执行中...", color: "text-blue-600", bg: "bg-blue-50 border-blue-100" },
    complete: { text: "已完成", color: "text-green-600", bg: "bg-green-50 border-green-100" },
    error: { text: "执行失败", color: "text-red-600", bg: "bg-red-50 border-red-100" },
  }[status];

  // 获取简略预览文字
  const getPreview = () => {
    if (!hasArgs) return "";
    const firstValue = Object.values(args)[0];
    if (typeof firstValue === "string") {
      return firstValue.length > 40 ? firstValue.slice(0, 40) + "..." : firstValue;
    }
    return "";
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15, delay: index * 0.03 }}
      className={cn("rounded-md border text-sm", statusConfig.bg)}
    >
      {/* 头部 - 可点击展开/收起 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        {/* 状态图标 */}
        {status === "running" ? (
          <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-blue-500" />
        ) : status === "complete" ? (
          <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-green-500" />
        ) : (
          <XCircle className="h-3.5 w-3.5 flex-shrink-0 text-red-500" />
        )}
        
        {/* 工具名称和状态 */}
        <span className={cn("font-medium", statusConfig.color)}>{toolLabel}</span>
        <span className="text-gray-400">-</span>
        <span className="text-gray-500">{statusConfig.text}</span>
        
        {/* 简略预览 */}
        {!isExpanded && getPreview() && (
          <span className="ml-1 flex-1 truncate text-gray-400">{getPreview()}</span>
        )}
        
        {/* 展开指示 */}
        {hasArgs && (
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.15 }}
            className="ml-auto flex-shrink-0"
          >
            <ChevronDown className="h-4 w-4 text-gray-400" />
          </motion.div>
        )}
      </button>
      
      {/* 展开的详细内容 */}
      <AnimatePresence>
        {isExpanded && hasArgs && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="border-t border-gray-200/50 bg-white/60 px-3 py-2 space-y-1.5">
              {Object.entries(args).map(([key, value], argIdx) => (
                <div key={argIdx} className="text-xs">
                  <span className="text-gray-500 uppercase">{key}:</span>
                  <div className="mt-0.5 text-gray-700">
                    {isComplexValue(value) ? (
                      <pre className="rounded bg-gray-50 p-1.5 text-xs overflow-auto max-h-32">
                        {JSON.stringify(value, null, 2)}
                      </pre>
                    ) : (
                      <span className="break-words">{String(value)}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/**
 * 工具调用组件 - 显示 AI 消息中的工具调用
 */
export function ToolCalls({
  toolCalls,
  status = "running",
}: {
  toolCalls: AIMessage["tool_calls"];
  status?: "running" | "complete" | "error";
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="space-y-1.5 my-2">
      {toolCalls.map((tc, idx) => {
        const uniqueKey = tc.id ? `${tc.id}-${idx}` : `tool-${idx}`;
        return (
          <ToolCallCard 
            key={uniqueKey} 
            toolCall={tc} 
            status={status}
            index={idx}
          />
        );
      })}
    </div>
  );
}

/**
 * 工具结果组件 - 显示工具执行结果
 */
export function ToolResult({ message }: { message: ToolMessage }) {
  const [isExpanded, setIsExpanded] = useState(false);

  let parsedContent: any;
  let isJsonContent = false;
  let isError = false;

  try {
    if (typeof message.content === "string") {
      parsedContent = JSON.parse(message.content);
      isJsonContent = isComplexValue(parsedContent);
      if (parsedContent.error || parsedContent.status === "error") {
        isError = true;
      }
    }
  } catch {
    parsedContent = message.content;
  }

  // 获取工具显示名称
  const toolLabel = toolNameMap[message.name || ""] || message.name || "工具结果";

  const contentStr = isJsonContent
    ? JSON.stringify(parsedContent, null, 2)
    : String(message.content);
  const shouldTruncate = contentStr.length > 100;

  // 获取简略预览
  const getPreview = () => {
    if (isJsonContent && parsedContent.message) {
      return parsedContent.message.slice(0, 50) + (parsedContent.message.length > 50 ? "..." : "");
    }
    return contentStr.slice(0, 50) + (contentStr.length > 50 ? "..." : "");
  };

  const statusConfig = isError 
    ? { text: "执行失败", color: "text-red-600", bg: "bg-red-50 border-red-100" }
    : { text: "执行完成", color: "text-green-600", bg: "bg-green-50 border-green-100" };

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className={cn("rounded-md border text-sm my-2", statusConfig.bg)}
    >
      {/* 头部 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        {/* 状态图标 */}
        {isError ? (
          <XCircle className="h-3.5 w-3.5 flex-shrink-0 text-red-500" />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-green-500" />
        )}
        
        {/* 工具名称和状态 */}
        <span className={cn("font-medium", statusConfig.color)}>{toolLabel}</span>
        <span className="text-gray-400">-</span>
        <span className="text-gray-500">{statusConfig.text}</span>
        
        {/* 简略预览 */}
        {!isExpanded && (
          <span className="ml-1 flex-1 truncate text-gray-400">{getPreview()}</span>
        )}
        
        {/* 展开指示 */}
        {shouldTruncate && (
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.15 }}
            className="ml-auto flex-shrink-0"
          >
            <ChevronDown className="h-4 w-4 text-gray-400" />
          </motion.div>
        )}
      </button>
      
      {/* 展开内容 */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="border-t border-gray-200/50 bg-white/60 px-3 py-2">
              <pre className="text-xs text-gray-700 whitespace-pre-wrap break-words max-h-48 overflow-auto">
                {contentStr}
              </pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
