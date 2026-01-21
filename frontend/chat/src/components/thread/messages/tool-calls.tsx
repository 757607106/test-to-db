/**
 * 工具调用组件
 * 
 * 基于官方 agent-chat-ui 实现，优化排版和展开收起功能
 * @see https://github.com/langchain-ai/agent-chat-ui
 */
import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Loader2, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

function isComplexValue(value: any): boolean {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

/**
 * 工具名称映射 - 将英文工具名转换为友好显示
 * 
 * 完整映射包括：
 * 1. Supervisor handoff 工具 (transfer_to_*)
 * 2. 各Agent的实际执行工具
 * 3. MCP 图表工具
 */
const toolNameMap: Record<string, string> = {
  // ===== Supervisor handoff 工具 =====
  transfer_to_schema_agent: "模式分析",
  transfer_to_sql_generator_agent: "SQL生成",
  transfer_to_sql_executor_agent: "SQL执行",
  transfer_to_chart_generator_agent: "图表生成",
  transfer_to_clarification_agent: "澄清问题",
  transfer_to_error_recovery_agent: "错误恢复",
  transfer_to_sample_retrieval_agent: "样本检索",
  
  // ===== Schema Agent 工具 =====
  analyze_user_query: "查询分析",
  retrieve_database_schema: "获取表结构",
  validate_schema_completeness: "验证完整性",
  
  // ===== SQL Generator Agent 工具 =====
  generate_sql_query: "SQL生成",
  generate_sql: "SQL生成",
  generate_sql_with_samples: "SQL生成(样本)",
  
  // ===== SQL Executor Agent 工具 =====
  execute_sql_query: "SQL执行",
  execute_sql: "SQL执行",
  
  // ===== Sample Retrieval Agent 工具 =====
  retrieve_similar_qa_pairs: "样本检索",
  analyze_sample_relevance: "样本分析",
  extract_sql_patterns: "SQL模式提取",
  
  // ===== Error Recovery Agent 工具 =====
  analyze_error_pattern: "错误分析",
  generate_recovery_strategy: "恢复策略",
  
  // ===== Chart Generator Agent 工具 (MCP) =====
  generate_chart: "图表生成",
  create_chart: "图表创建",
  "mcp-chart": "图表生成",
  chart: "图表创建",
  
  // ===== Clarification Agent 工具 =====
  quick_clarification_check: "澄清检测",
  generate_clarification_questions: "生成澄清问题",
};

/**
 * 获取工具显示名称
 */
function getToolLabel(name: string | undefined): string {
  if (!name) return "工具调用";
  return toolNameMap[name] || name;
}

/**
 * 单个工具调用卡片
 */
function ToolCallCard({ 
  toolCall, 
  index,
  messageId,
  isComplete,
}: { 
  toolCall: NonNullable<AIMessage["tool_calls"]>[number];
  index: number;
  messageId?: string;
  isComplete?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const args = (toolCall.args || {}) as Record<string, any>;
  const hasArgs = Object.keys(args).length > 0;
  const toolLabel = getToolLabel(toolCall.name);

  // 根据状态设置样式
  const statusStyle = isComplete 
    ? { border: "border-green-100", bg: "bg-green-50/50", hover: "hover:bg-green-50", text: "text-green-700" }
    : { border: "border-blue-100", bg: "bg-blue-50/50", hover: "hover:bg-blue-50", text: "text-blue-700" };

  // 获取简短预览
  const getPreview = () => {
    if (!hasArgs) return "";
    const firstValue = Object.values(args)[0];
    if (typeof firstValue === "string") {
      return firstValue.length > 30 ? firstValue.slice(0, 30) + "..." : firstValue;
    }
    return "";
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15, delay: index * 0.03 }}
      className={cn("overflow-hidden rounded-lg border", statusStyle.border, statusStyle.bg)}
    >
      {/* 头部 - 可点击展开/收起 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn("flex w-full items-center gap-2 px-3 py-2 text-left transition-colors", statusStyle.hover)}
      >
        {isComplete ? (
          <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-green-500" />
        ) : (
          <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-blue-500" />
        )}
        <span className={cn("font-medium text-sm", statusStyle.text)}>{toolLabel}</span>
        
        {/* 简短预览 */}
        {!isExpanded && getPreview() && (
          <span className="ml-1 flex-1 truncate text-xs text-gray-400">{getPreview()}</span>
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
            <div className="border-t border-blue-100 bg-white px-3 py-2 space-y-1">
              {Object.entries(args).map(([key, value], argIdx) => (
                <div key={argIdx} className="text-xs">
                  <span className="text-gray-500 font-medium">{key}: </span>
                  {isComplexValue(value) ? (
                    <pre className="mt-1 rounded bg-gray-50 p-2 text-xs overflow-auto max-h-24 text-gray-600">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ) : (
                    <span className="text-gray-700 break-words">{String(value)}</span>
                  )}
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
 * 工具调用组件
 */
export function ToolCalls({
  toolCalls,
  messageId,
  completedToolIds,
}: {
  toolCalls: AIMessage["tool_calls"];
  messageId?: string;
  completedToolIds?: Set<string>;
}) {
  // ✅ 修复：去重和过滤 toolCalls 数组
  // 问题：流式传输时，同一个工具调用会被多次添加到数组中，且后续项可能缺少 name
  // 解决：按 ID 去重，保留有 name 的完整版本，过滤掉空的工具调用
  const dedupedToolCalls = (() => {
    if (!toolCalls || toolCalls.length === 0) return [];
    
    const seenIds = new Map<string, typeof toolCalls[number]>();
    const noIdCalls: typeof toolCalls[number][] = [];
    
    for (const tc of toolCalls) {
      // 过滤掉完全空的工具调用（没有 ID 且没有 name）
      if (!tc.id && !tc.name) {
        continue;
      }
      
      if (tc.id) {
        // 按 ID 去重，保留有 name 的版本
        const existing = seenIds.get(tc.id);
        if (!existing || (tc.name && !existing.name)) {
          seenIds.set(tc.id, tc);
        }
      } else if (tc.name) {
        // 没有 ID 但有 name 的情况（罕见）
        noIdCalls.push(tc);
      }
    }
    
    return [...seenIds.values(), ...noIdCalls];
  })();

  if (dedupedToolCalls.length === 0) return null;

  return (
    <div className="space-y-1.5 my-2">
      {dedupedToolCalls.map((tc, idx) => {
        const uniqueKey = `${messageId || 'msg'}-${idx}-${tc.id || 'unknown'}`;
        const isComplete = tc.id ? completedToolIds?.has(tc.id) : false;
        return (
          <ToolCallCard 
            key={uniqueKey} 
            toolCall={tc} 
            index={idx}
            messageId={messageId}
            isComplete={isComplete}
          />
        );
      })}
    </div>
  );
}

/**
 * 工具结果组件
 */
export function ToolResult({ message }: { message: ToolMessage }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const toolLabel = getToolLabel(message.name);

  let parsedContent: any;
  let isJsonContent = false;
  let isError = false;
  let statusText = "";

  try {
    if (typeof message.content === "string") {
      parsedContent = JSON.parse(message.content);
      isJsonContent = isComplexValue(parsedContent);
      // 检查状态
      if (parsedContent.status === "error" || parsedContent.error) {
        isError = true;
        statusText = parsedContent.error || "执行失败";
      } else if (parsedContent.status === "success") {
        statusText = "执行成功";
      }
    }
  } catch {
    parsedContent = message.content;
  }

  // 获取简短预览
  const getPreview = () => {
    if (statusText) return statusText;
    if (typeof parsedContent === "string") {
      return parsedContent.length > 40 ? parsedContent.slice(0, 40) + "..." : parsedContent;
    }
    if (isJsonContent && parsedContent.data) {
      const dataStr = JSON.stringify(parsedContent.data);
      return dataStr.length > 40 ? dataStr.slice(0, 40) + "..." : dataStr;
    }
    return "";
  };

  const contentStr = isJsonContent
    ? JSON.stringify(parsedContent, null, 2)
    : String(message.content);
  const shouldTruncate = contentStr.length > 200;

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className={cn(
        "overflow-hidden rounded-lg border my-2",
        isError ? "border-red-100 bg-red-50/50" : "border-green-100 bg-green-50/50"
      )}
    >
      {/* 头部 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          "flex w-full items-center gap-2 px-3 py-2 text-left transition-colors",
          isError ? "hover:bg-red-50" : "hover:bg-green-50"
        )}
      >
        <CheckCircle2 className={cn(
          "h-3.5 w-3.5 flex-shrink-0",
          isError ? "text-red-500" : "text-green-500"
        )} />
        <span className={cn(
          "font-medium text-sm",
          isError ? "text-red-700" : "text-green-700"
        )}>{toolLabel}</span>
        
        {/* 简短预览 */}
        {!isExpanded && (
          <span className="ml-1 flex-1 truncate text-xs text-gray-400">{getPreview()}</span>
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
            <div className={cn(
              "border-t px-3 py-2 bg-white",
              isError ? "border-red-100" : "border-green-100"
            )}>
              <pre className="text-xs text-gray-600 whitespace-pre-wrap break-words max-h-60 overflow-auto">
                {contentStr}
              </pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
