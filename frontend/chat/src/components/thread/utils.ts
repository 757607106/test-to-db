import type { Message } from "@langchain/langgraph-sdk";

/**
 * 检测内容是否是原始 JSON 工具数据
 * 
 * 这些数据应该通过工具调用组件显示，而不是作为文本渲染
 */
function isRawToolData(content: string): boolean {
  const trimmed = content.trim();
  
  // 检测完整 JSON：以 { 或 [ 开头
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    return true;
  }
  
  // 检测 JSON 片段（流式传输可能导致分块）
  // 以 }, 或 }, { 或 }] 或 ], 等开头
  if (/^[}\]],?\s*[{[]?/.test(trimmed)) {
    return true;
  }
  
  // 检测 JSON 字段名模式："field_name":
  if (/^\s*"[a-z_]+":\s*/.test(trimmed)) {
    return true;
  }
  
  // 检测 SQL 语句
  if (trimmed.startsWith("SELECT ") || trimmed.startsWith("INSERT ") || 
      trimmed.startsWith("UPDATE ") || trimmed.startsWith("DELETE ")) {
    return true;
  }
  
  // 检测包含工具特征的内容
  const toolPatterns = [
    '"needs_clarification"',
    '"clarification_questions"',
    '"filtered_tables"',
    '"question_id"',
    '"analysis_summary"',
    '"ambiguities"'
  ];
  if (toolPatterns.some(p => trimmed.includes(p))) {
    return true;
  }
  
  return false;
}

/**
 * 从消息内容中提取文本字符串
 * 
 * 遵循 LangGraph SDK 官方标准：
 * - 支持字符串和多模态内容（text, image, file 等）
 * - 工具结果在 ToolResult 组件中单独显示
 * - 过滤掉原始 JSON 工具数据（应该通过工具组件显示）
 * 
 * @see https://github.com/langchain-ai/agent-chat-ui
 */
export function getContentString(content: Message["content"]): string {
  // 字符串内容处理
  if (typeof content === "string") {
    // 过滤掉原始 JSON 工具数据
    if (isRawToolData(content)) {
      return "";
    }
    return content;
  }
  
  // 空内容返回空字符串
  if (!content || !Array.isArray(content)) return "";

  // 提取所有文本内容（过滤掉原始工具数据）
  const texts = content
    .filter((c): c is { type: "text"; text: string } => c.type === "text" && typeof c.text === "string")
    .map((c) => c.text)
    .filter((text) => !isRawToolData(text));

  return texts.join(" ");
}

/**
 * 检查消息是否有实质性内容
 * 
 * 用于判断是否需要渲染消息组件
 */
export function hasSubstantialContent(message: Message): boolean {
  // AI 消息：有文本内容或工具调用
  if (message.type === "ai") {
    const content = getContentString(message.content);
    const hasToolCalls = "tool_calls" in message && Array.isArray(message.tool_calls) && message.tool_calls.length > 0;
    return content.length > 0 || Boolean(hasToolCalls);
  }
  
  // 工具消息：始终有内容
  if (message.type === "tool") {
    return true;
  }
  
  // 人类消息：有内容
  if (message.type === "human") {
    return getContentString(message.content).length > 0;
  }
  
  return false;
}

// ============================================================================
// 数据转换工具函数
// ============================================================================

/**
 * 将后端返回的数组数组格式转换为对象数组格式
 * 
 * 后端可能返回两种格式:
 * 1. 数组数组: [[val1, val2], [val3, val4]]
 * 2. 对象数组: [{col1: val1, col2: val2}] (已是目标格式)
 * 
 * @param columns - 列名数组
 * @param rows - 数据行（可能是数组数组或对象数组）
 * @returns 对象数组格式的数据
 */
export function transformQueryData(
  columns: string[],
  rows: any[]
): Record<string, any>[] {
  if (!rows || rows.length === 0) {
    return [];
  }
  
  // 检查第一行是否已经是对象格式
  const firstRow = rows[0];
  if (firstRow && typeof firstRow === "object" && !Array.isArray(firstRow)) {
    // 已经是对象数组格式，直接返回
    return rows as Record<string, any>[];
  }
  
  // 数组数组格式，转换为对象数组
  return rows.map((row: any[]) => {
    const obj: Record<string, any> = {};
    columns.forEach((col, idx) => {
      obj[col] = row[idx];
    });
    return obj;
  });
}

/**
 * 格式化数值用于显示
 * 
 * @param value - 原始值
 * @param precision - 小数位数 (默认 2)
 * @returns 格式化后的字符串
 */
export function formatDisplayValue(value: any, precision: number = 2): string {
  if (value === null || value === undefined) {
    return "-";
  }
  
  if (typeof value === "number") {
    // 整数不显示小数
    if (Number.isInteger(value)) {
      return value.toLocaleString();
    }
    // 浮点数保留指定小数位
    return value.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: precision,
    });
  }
  
  return String(value);
}

/**
 * 节点名称映射：将后端新节点名映射到 UI 显示名
 */
export const NODE_DISPLAY_NAMES: Record<string, string> = {
  // Hub-and-Spoke 节点
  schema_agent: "Schema 分析",
  clarification: "需求澄清",
  sql_generator: "SQL 生成",
  sql_executor: "SQL 执行",
  data_analyst: "数据分析",
  chart_generator: "图表生成",
  error_recovery: "错误恢复",
  general_chat: "闲聊处理",
  // 旧版节点（兼容）
  schema_mapping: "Schema 映射",
  few_shot: "Few-shot 示例",
  llm_parse: "LLM 解析",
  sql_fix: "SQL 修正",
  final_sql: "SQL 执行",
  data_analysis: "数据分析",
  chart_generation: "图表生成",
};
