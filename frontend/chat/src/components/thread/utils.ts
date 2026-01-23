import type { Message } from "@langchain/langgraph-sdk";

/**
 * 检测内容是否是原始 JSON 工具数据
 * 
 * 这些数据应该通过工具调用组件显示，而不是作为文本渲染
 */
function isRawToolData(content: string): boolean {
  if (!content.startsWith("{") && !content.startsWith("[")) {
    return false;
  }
  
  try {
    const parsed = JSON.parse(content);
    // 检测常见的工具返回格式
    if (typeof parsed === "object" && parsed !== null) {
      // ToolResponse 格式
      if ("status" in parsed && ["success", "error", "pending"].includes(parsed.status)) {
        return true;
      }
      // 分析结果格式
      if ("analysis" in parsed || "relevant_tables" in parsed || "schema_context" in parsed) {
        return true;
      }
      // SQL 生成结果格式
      if ("sql_query" in parsed || "generated_sql" in parsed) {
        return true;
      }
    }
  } catch {
    // 不是有效 JSON，当作普通文本
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
