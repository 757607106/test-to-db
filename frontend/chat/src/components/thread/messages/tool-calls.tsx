/**
 * 工具调用组件
 * 
 * 基于 LangGraph SDK 官方标准实现
 * 统一显示工具调用和工具结果
 * 
 * @see https://github.com/langchain-ai/agent-chat-ui
 */
import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";
import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, CheckCircle2, XCircle } from "lucide-react";
import { parseToolResult, isToolSuccess, isToolError } from "@/types/agent-message";

function isComplexValue(value: unknown): boolean {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

/**
 * 工具名称映射 - 将英文工具名转换为友好显示
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
 * 工具调用组件 - 官方实现
 */
export function ToolCalls({
  toolCalls,
}: {
  toolCalls: AIMessage["tool_calls"];
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2">
      {toolCalls.map((tc, idx) => {
        const args = tc.args as Record<string, any>;
        const hasArgs = Object.keys(args).length > 0;
        const toolLabel = getToolLabel(tc.name);

        return (
          <div
            key={idx}
            className="overflow-hidden rounded-lg border border-gray-200"
          >
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-2">
              <h3 className="font-medium text-gray-900">
                {toolLabel}
                {tc.id && (
                  <code className="ml-2 rounded bg-gray-100 px-2 py-1 text-sm">
                    {tc.id}
                  </code>
                )}
              </h3>
            </div>

            {hasArgs ? (
              <table className="min-w-full divide-y divide-gray-200">
                <tbody className="divide-y divide-gray-200">
                  {Object.entries(args).map(([key, value], argIdx) => (
                    <tr key={argIdx}>
                      <td className="px-4 py-2 text-sm font-medium whitespace-nowrap text-gray-900">
                        {key}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-500">
                        {isComplexValue(value) ? (
                          <code className="rounded bg-gray-50 px-2 py-1 font-mono text-sm break-all">
                            {JSON.stringify(value, null, 2)}
                          </code>
                        ) : (
                          String(value)
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <code className="block p-3 text-sm">{"{}"}</code>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * 工具结果组件
 * 
 * 统一解析和显示工具执行结果
 * 支持后端统一的 ToolResponse 格式
 */
export function ToolResult({ message }: { message: ToolMessage }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const toolLabel = getToolLabel(message.name);

  // 使用 useMemo 避免重复解析
  const { parsedResult, isSuccess, displayData, hasExpandableContent } = useMemo(() => {
    // 尝试使用统一的 ToolResponse 解析
    const parsed = parseToolResult(message.content);
    const success = isToolSuccess(parsed);
    
    // 提取要显示的数据
    let data: unknown = parsed.data;
    let expandable = false;
    
    // 如果是成功的结果，优先显示 data 字段
    if (success && parsed.data) {
      data = parsed.data;
      // 检查是否有可展开的内容
      if (typeof data === "object" && data !== null) {
        const dataObj = data as Record<string, unknown>;
        // SQL 查询结果通常有 data 数组
        if (Array.isArray(dataObj.data) && dataObj.data.length > 5) {
          expandable = true;
        } else if (Array.isArray(data) && (data as unknown[]).length > 5) {
          expandable = true;
        }
      }
    } else if (parsed.error) {
      data = { error: parsed.error };
    }
    
    return {
      parsedResult: parsed,
      isSuccess: success,
      displayData: data,
      hasExpandableContent: expandable,
    };
  }, [message.content]);

  // 格式化显示内容
  const formatDisplayContent = () => {
    if (!displayData) return "无数据";
    
    if (typeof displayData === "string") {
      return displayData;
    }
    
    // 对于对象/数组，格式化为 JSON
    return JSON.stringify(displayData, null, 2);
  };

  const displayContent = formatDisplayContent();
  const shouldTruncate = displayContent.length > 500 || displayContent.split("\n").length > 10;

  return (
    <div className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2">
      <div className="overflow-hidden rounded-lg border border-gray-200">
        {/* 标题栏 - 显示状态指示器 */}
        <div className={`border-b px-4 py-2 ${isSuccess ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}`}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {isSuccess ? (
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              ) : (
                <XCircle className="h-4 w-4 text-red-600" />
              )}
              <h3 className="font-medium text-gray-900">
                {toolLabel}
              </h3>
            </div>
            
            {/* 元数据显示 */}
            {parsedResult.metadata?.execution_time && (
              <span className="text-xs text-gray-500">
                {(parsedResult.metadata.execution_time as number).toFixed(2)}s
              </span>
            )}
          </div>
        </div>

        {/* 内容区域 */}
        <motion.div
          className="min-w-full bg-gray-50"
          initial={false}
          animate={{ height: "auto" }}
          transition={{ duration: 0.3 }}
        >
          <div className="p-3">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={isExpanded ? "expanded" : "collapsed"}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                {/* 显示结构化数据 */}
                {typeof displayData === "object" && displayData !== null ? (
                  <StructuredDataDisplay 
                    data={displayData as Record<string, unknown>} 
                    isExpanded={isExpanded} 
                  />
                ) : (
                  <code className="block text-sm whitespace-pre-wrap break-all">
                    {shouldTruncate && !isExpanded 
                      ? displayContent.slice(0, 500) + "..." 
                      : displayContent}
                  </code>
                )}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* 展开/收起按钮 */}
          {(shouldTruncate || hasExpandableContent) && (
            <motion.button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex w-full cursor-pointer items-center justify-center border-t border-gray-200 py-2 text-gray-500 transition-all hover:bg-gray-100 hover:text-gray-700"
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
            >
              {isExpanded ? (
                <>
                  <ChevronUp className="h-4 w-4 mr-1" />
                  <span className="text-sm">收起</span>
                </>
              ) : (
                <>
                  <ChevronDown className="h-4 w-4 mr-1" />
                  <span className="text-sm">展开更多</span>
                </>
              )}
            </motion.button>
          )}
        </motion.div>
      </div>
    </div>
  );
}

/**
 * 结构化数据显示组件
 */
function StructuredDataDisplay({ 
  data, 
  isExpanded 
}: { 
  data: Record<string, unknown>; 
  isExpanded: boolean;
}) {
  // SQL 查询结果特殊处理
  if ("columns" in data && "data" in data && Array.isArray(data.data)) {
    const columns = data.columns as string[];
    const rows = data.data as unknown[][];
    const displayRows = isExpanded ? rows : rows.slice(0, 5);
    
    return (
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-100">
            <tr>
              {columns.map((col, idx) => (
                <th key={idx} className="px-3 py-2 text-left font-medium text-gray-700">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {displayRows.map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-gray-50">
                {(row as unknown[]).map((cell, cellIdx) => (
                  <td key={cellIdx} className="px-3 py-2 text-gray-600">
                    {isComplexValue(cell) 
                      ? JSON.stringify(cell) 
                      : String(cell ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {!isExpanded && rows.length > 5 && (
          <div className="text-center text-xs text-gray-500 py-2">
            还有 {rows.length - 5} 行未显示
          </div>
        )}
      </div>
    );
  }
  
  // 通用对象显示
  const entries = Object.entries(data);
  const displayEntries = isExpanded ? entries : entries.slice(0, 10);
  
  return (
    <table className="min-w-full divide-y divide-gray-200">
      <tbody className="divide-y divide-gray-100">
        {displayEntries.map(([key, value], idx) => (
          <tr key={idx}>
            <td className="px-3 py-2 text-sm font-medium text-gray-700 whitespace-nowrap">
              {key}
            </td>
            <td className="px-3 py-2 text-sm text-gray-600">
              {isComplexValue(value) ? (
                <code className="rounded bg-gray-100 px-2 py-1 font-mono text-xs break-all block max-h-40 overflow-auto">
                  {JSON.stringify(value, null, 2)}
                </code>
              ) : (
                String(value ?? "")
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
