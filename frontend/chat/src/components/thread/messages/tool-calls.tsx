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
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, Circle, Database, Code, Zap } from "lucide-react";
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
 * 工具调用组件
 */
export function ToolCalls({
  toolCalls,
}: {
  toolCalls: AIMessage["tool_calls"];
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="space-y-2">
      {toolCalls.map((tc, idx) => (
        <ToolCallCard key={tc.id || idx} toolCall={tc} />
      ))}
    </div>
  );
}

/**
 * 工具调用卡片 - 显示调用中状态
 */
function ToolCallCard({ toolCall }: { toolCall: AIMessage["tool_calls"][0] }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const args = toolCall.args as Record<string, any>;
  const hasArgs = Object.keys(args).length > 0;
  const toolLabel = getToolLabel(toolCall.name);

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* 头部 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors"
      >
        <motion.div
          animate={{ rotate: isExpanded ? 90 : 0 }}
          transition={{ duration: 0.2 }}
          className="text-slate-400"
        >
          <ChevronRight className="h-4 w-4" />
        </motion.div>
        
        <div className="flex items-center gap-2">
          <Circle className="h-2 w-2 fill-blue-500 text-blue-500" />
          <span className="text-sm font-medium text-slate-700">{toolLabel}</span>
        </div>
        
        <span className="ml-auto text-xs text-slate-400 font-mono">
          {toolCall.id ? `#${toolCall.id.slice(-8)}` : ''}
        </span>
      </button>

      {/* 参数内容 */}
      <AnimatePresence>
        {isExpanded && hasArgs && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="border-t border-slate-100 bg-slate-50/50">
              <div className="divide-y divide-slate-100">
                {Object.entries(args).map(([key, value]) => (
                  <div key={key} className="flex">
                    <div className="w-36 flex-shrink-0 px-4 py-2.5 text-xs font-medium text-slate-500 bg-slate-50">
                      {key}
                    </div>
                    <div className="flex-1 px-4 py-2.5 text-sm text-slate-700 break-all">
                      {isComplexValue(value) ? (
                        <code className="text-xs bg-slate-100 px-2 py-1 rounded font-mono block whitespace-pre-wrap">
                          {JSON.stringify(value, null, 2)}
                        </code>
                      ) : (
                        String(value)
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

/**
 * 工具结果组件
 */
export function ToolResult({ message }: { message: ToolMessage }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const toolLabel = getToolLabel(message.name);

  const { parsedResult, isSuccess, displayData } = useMemo(() => {
    const parsed = parseToolResult(message.content);
    const success = isToolSuccess(parsed);
    
    let data: unknown = parsed.data;
    
    // 如果 data 为空但有其他字段（如 columns, rows），使用整个解析结果
    if (!data && parsed && typeof parsed === 'object') {
      const keys = Object.keys(parsed).filter(k => k !== 'status' && k !== 'error');
      if (keys.length > 0) {
        data = parsed;
      }
    }
    
    // 如果是错误，显示错误信息
    if (!success && parsed.error) {
      data = { error: parsed.error };
    }
    
    return {
      parsedResult: parsed,
      isSuccess: success,
      displayData: data,
    };
  }, [message.content]);

  const borderColor = isSuccess ? "border-emerald-200" : "border-red-200";
  const headerBg = isSuccess ? "bg-emerald-50" : "bg-red-50";
  const statusColor = isSuccess ? "text-emerald-600" : "text-red-600";
  const statusBg = isSuccess ? "bg-emerald-100" : "bg-red-100";

  return (
    <div className={`rounded-lg border ${borderColor} bg-white shadow-sm overflow-hidden`}>
      {/* 头部 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full flex items-center gap-3 px-4 py-3 ${headerBg} hover:brightness-95 transition-all`}
      >
        <motion.div
          animate={{ rotate: isExpanded ? 90 : 0 }}
          transition={{ duration: 0.2 }}
          className="text-slate-400"
        >
          <ChevronRight className="h-4 w-4" />
        </motion.div>
        
        <div className="flex items-center gap-2">
          {isSuccess ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          ) : (
            <XCircle className="h-4 w-4 text-red-500" />
          )}
          <span className="text-sm font-medium text-slate-700">{toolLabel}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${statusBg} ${statusColor}`}>
            {isSuccess ? "成功" : "失败"}
          </span>
        </div>
        
        {parsedResult.metadata?.execution_time && (
          <span className="ml-auto text-xs text-slate-400">
            {(parsedResult.metadata.execution_time as number).toFixed(2)}s
          </span>
        )}
      </button>

      {/* 结果内容 */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="border-t border-slate-100 p-4">
              {typeof displayData === "object" && displayData !== null ? (
                <DataDisplay data={displayData as Record<string, unknown>} isSuccess={isSuccess} />
              ) : (
                <code className="block text-sm whitespace-pre-wrap break-all bg-slate-50 rounded-lg p-3 border border-slate-200">
                  {displayData ? String(displayData) : "无数据"}
                </code>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * 数据展示组件
 */
function DataDisplay({ 
  data, 
  isSuccess = true 
}: { 
  data: Record<string, unknown>; 
  isSuccess?: boolean;
}) {
  // SQL 查询结果 - 表格展示
  // 支持两种格式：
  // 1. {columns: [...], data: [...]}
  // 2. {columns: [...], rows: [...]}
  const hasColumns = "columns" in data && Array.isArray(data.columns);
  const rowsData = data.data || data.rows;
  const hasRows = Array.isArray(rowsData);
  
  if (hasColumns && hasRows) {
    const columns = data.columns as string[];
    const rows = rowsData as unknown[][];
    
    if (rows.length === 0) {
      return (
        <div className="text-center py-6 text-slate-500 text-sm">
          查询结果为空
        </div>
      );
    }
    
    return (
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              {columns.map((col, idx) => (
                <th key={idx} className="px-4 py-2.5 text-left font-semibold text-slate-600 border-b border-slate-200">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-slate-100">
            {rows.slice(0, 10).map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-slate-50 transition-colors">
                {(row as unknown[]).map((cell, cellIdx) => (
                  <td key={cellIdx} className="px-4 py-2.5 text-slate-700">
                    {isComplexValue(cell) 
                      ? <code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">{JSON.stringify(cell)}</code>
                      : String(cell ?? "-")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > 10 && (
          <div className="text-center text-xs text-slate-500 py-2 bg-slate-50 border-t border-slate-200">
            显示前 10 条，共 {rows.length} 条数据
          </div>
        )}
      </div>
    );
  }
  
  // 错误信息
  if ("error" in data) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 p-4">
        <div className="flex items-start gap-3">
          <XCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-medium text-red-700 mb-1">错误信息</div>
            <code className="text-sm text-red-600 whitespace-pre-wrap break-all">
              {String(data.error)}
            </code>
          </div>
        </div>
      </div>
    );
  }
  
  // 通用键值对展示
  const entries = Object.entries(data);
  
  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <div className="divide-y divide-slate-100">
        {entries.map(([key, value]) => (
          <div key={key} className="flex">
            <div className="w-40 flex-shrink-0 px-4 py-2.5 text-xs font-medium text-slate-500 bg-slate-50">
              {key}
            </div>
            <div className="flex-1 px-4 py-2.5 text-sm text-slate-700 break-all bg-white">
              {isComplexValue(value) ? (
                <code className="text-xs bg-slate-100 px-2 py-1 rounded font-mono block whitespace-pre-wrap max-h-48 overflow-auto">
                  {JSON.stringify(value, null, 2)}
                </code>
              ) : (
                String(value ?? "-")
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
