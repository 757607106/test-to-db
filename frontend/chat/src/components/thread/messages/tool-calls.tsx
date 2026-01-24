/**
 * 工具调用组件
 * 
 * 优化后的现代化卡片设计
 */
import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ChevronDown, 
  ChevronUp, 
  Terminal, 
  Loader2, 
  CheckCircle2,
  AlertCircle,
  FileText
} from "lucide-react";
import { cn } from "@/lib/utils";

function isComplexValue(value: any): boolean {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

interface ToolCallsProps {
  toolCalls: AIMessage["tool_calls"];
  isLoading?: boolean;
}

function ToolCallItem({ tc, isRunning }: { tc: NonNullable<AIMessage["tool_calls"]>[number], isRunning: boolean }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const args = tc.args as Record<string, any>;
  const hasArgs = Object.keys(args).length > 0;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border transition-all duration-200",
        isRunning 
          ? "border-blue-200 bg-blue-50/30 dark:border-blue-800 dark:bg-blue-900/10 shadow-md" 
          : "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 shadow-sm"
      )}
    >
      {/* Header */}
      <div 
        className="flex items-center justify-between px-4 py-3 border-b border-transparent hover:border-slate-100 dark:hover:border-slate-800 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            "p-2 rounded-lg",
            isRunning 
              ? "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400" 
              : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
          )}>
            <Terminal className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-sm text-slate-800 dark:text-slate-200">
              {tc.name}
            </span>
            {tc.id && (
              <span className="text-xs text-slate-400 font-mono">
                {tc.id}
              </span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {isRunning ? (
            <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-blue-100/50 dark:bg-blue-900/20">
              <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin" />
              <span className="text-xs font-medium text-blue-600">执行中...</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-emerald-500 dark:text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
              <span className="text-xs font-medium">已调用</span>
            </div>
          )}
          
          <div className="text-slate-400">
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </div>
      </div>

      {/* Body (Arguments) */}
      <AnimatePresence initial={false}>
        {hasArgs && isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="p-3 bg-slate-50/50 dark:bg-slate-950/30 border-t border-slate-100 dark:border-slate-800">
              <div className="grid gap-2">
                {Object.entries(args).map(([key, value], argIdx) => (
                  <div key={argIdx} className="flex flex-col gap-1 sm:flex-row sm:gap-4">
                    <span className="text-xs font-medium text-slate-500 min-w-[80px] pt-1">
                      {key}
                    </span>
                    <div className="flex-1 min-w-0">
                      {isComplexValue(value) ? (
                        <div className="rounded-md bg-slate-100 dark:bg-slate-800 p-2 overflow-x-auto">
                          <pre className="text-xs font-mono text-slate-700 dark:text-slate-300">
                            {JSON.stringify(value, null, 2)}
                          </pre>
                        </div>
                      ) : (
                        <div className="text-sm text-slate-700 dark:text-slate-300 break-words font-mono bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded px-2 py-1">
                          {String(value)}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function ToolCalls({
  toolCalls,
  isLoading = false
}: ToolCallsProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 my-2 w-full max-w-3xl">
      {toolCalls.map((tc, idx) => {
        // 状态逻辑：
        // 如果整体 isLoading 为 true，且是最后一个工具调用，则认为正在运行
        // 否则认为是已完成
        const isRunning = isLoading && idx === toolCalls.length - 1;

        return (
          <ToolCallItem key={idx} tc={tc} isRunning={isRunning} />
        );
      })}
    </div>
  );
}

export function ToolResult({ message }: { message: ToolMessage }) {
  const [isExpanded, setIsExpanded] = useState(false);

  let parsedContent: any;
  let isJsonContent = false;
  let isError = false;

  // 简单的错误检测逻辑
  if (message.status === "error" || (typeof message.content === "string" && message.content.toLowerCase().includes("error"))) {
    isError = true;
  }

  try {
    if (typeof message.content === "string") {
      parsedContent = JSON.parse(message.content);
      isJsonContent = isComplexValue(parsedContent);
    }
  } catch {
    // Content is not JSON, use as is
    parsedContent = message.content;
  }

  const contentStr = isJsonContent
    ? JSON.stringify(parsedContent, null, 2)
    : String(message.content);
  
  // 渲染逻辑优化
  // 如果内容较长，我们还是使用折叠逻辑，但默认状态改为展开
  // 点击 Header 切换展开/收起
  // 去除底部的"展开/收起"按钮，改为 Header 交互

  return (
    <div className="flex flex-col my-2 w-full max-w-3xl">
      <div className={cn(
        "overflow-hidden rounded-xl border shadow-sm transition-all",
        isError
          ? "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/20"
          : "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
      )}>
        {/* Header - 可点击 */}
        <div 
          className={cn(
            "flex items-center justify-between px-4 py-3 border-b cursor-pointer transition-colors",
            isError 
              ? "border-red-100 bg-red-50/50 hover:bg-red-100/50 dark:border-red-900/50 dark:bg-red-900/10 dark:hover:bg-red-900/20" 
              : "border-slate-100 bg-slate-50/50 hover:bg-slate-100/50 dark:border-slate-800 dark:bg-slate-900/50 dark:hover:bg-slate-800/50"
          )}
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center gap-3">
            <div className={cn(
              "p-2 rounded-lg",
              isError 
                ? "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400" 
                : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
            )}>
              {isError ? <AlertCircle className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
            </div>
            <div className="flex flex-col">
              <span className={cn(
                "font-semibold text-sm",
                isError ? "text-red-700 dark:text-red-400" : "text-slate-800 dark:text-slate-200"
              )}>
                {message.name ? `Result: ${message.name}` : "Tool Result"}
              </span>
              {message.tool_call_id && (
                <span className="text-xs text-slate-400 font-mono">
                  {message.tool_call_id}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
             {isError && (
               <span className="text-xs font-medium text-red-600 bg-red-100 px-2 py-1 rounded-full dark:bg-red-900/30 dark:text-red-400">
                 Error
               </span>
             )}
             <div className="text-slate-400">
               {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
             </div>
          </div>
        </div>
        
        {/* Body */}
        <AnimatePresence initial={false}>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className="p-3 bg-white dark:bg-slate-950">
                  {isJsonContent ? (
                    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 overflow-hidden">
                      <div className="overflow-x-auto p-3">
                         <table className="min-w-full text-left text-sm">
                           <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                              {(Array.isArray(parsedContent)
                                ? parsedContent
                                : Object.entries(parsedContent)
                              ).map((item, argIdx) => {
                                const [key, value] = Array.isArray(parsedContent)
                                  ? [argIdx, item]
                                  : [item[0], item[1]];
                                return (
                                  <tr key={argIdx}>
                                    <td className="py-2 pr-4 font-medium text-slate-600 dark:text-slate-400 whitespace-nowrap align-top">
                                      {key}
                                    </td>
                                    <td className="py-2 text-slate-800 dark:text-slate-200 break-all">
                                      {isComplexValue(value) ? (
                                        <pre className="text-xs font-mono bg-white dark:bg-slate-900 p-2 rounded border border-slate-200 dark:border-slate-700">
                                          {JSON.stringify(value, null, 2)}
                                        </pre>
                                      ) : (
                                        String(value)
                                      )}
                                    </td>
                                  </tr>
                                );
                              })}
                           </tbody>
                         </table>
                      </div>
                    </div>
                  ) : (
                    <div className="font-mono text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap break-words bg-slate-50 dark:bg-slate-950 p-3 rounded-lg border border-slate-200 dark:border-slate-700">
                      {contentStr}
                    </div>
                  )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
