import type { Message } from "@langchain/langgraph-sdk";

/**
 * 检测字符串是否看起来像 JSON 数据
 * 用于过滤工具返回的原始 JSON，避免在 AI 消息中显示
 */
function looksLikeJson(text: string): boolean {
  const trimmed = text.trim();
  // 检查是否以 { 或 [ 开头，以 } 或 ] 结尾
  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try {
      JSON.parse(trimmed);
      return true;
    } catch {
      return false;
    }
  }
  return false;
}

/**
 * 检测字符串是否是工具结果的典型特征
 * 包括：
 * - JSON 格式的分析结果（包含 analysis, entities, status 等字段）
 * - Python repr 格式的工具结果（status='success' data={...}）
 * - 工具返回的数据结构
 */
function isToolResultContent(text: string): boolean {
  const trimmed = text.trim();
  
  // 检测 Python repr 格式：status='success' data={...}
  // 或者 status='error' error='...'
  if (/^status=['"](success|error)['"]/.test(trimmed)) {
    return true;
  }
  
  // 检测纯 Python dict 格式（以 { 开头，包含单引号键）
  if (trimmed.startsWith('{') && trimmed.includes("'")) {
    // 检查是否包含工具结果的典型字段（Python 格式使用单引号）
    const pythonToolResultPatterns = [
      /'analysis':/,
      /'entities':/,
      /'relationships':/,
      /'query_intent':/,
      /'relevant_tables':/,
      /'table_id':/,
      /'relevance_score':/,
      /'reasoning':/,
      /'status':/,
      /'data':/,
      /'error':/,
      /'sql':/,
      /'result':/,
      /'include':/,
      /'likely_aggregations':/,
      /'time_related':/,
      /'comparison_related':/,
    ];
    if (pythonToolResultPatterns.some(pattern => pattern.test(trimmed))) {
      return true;
    }
  }
  
  // 检测数组格式的工具结果（如表选择结果）
  // [ { "table_id": 33, "include": false, "reasoning": "..." }, ... ]
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'object') {
        const toolResultFields = ['table_id', 'include', 'reasoning', 'relevance_score'];
        const hasToolResultField = toolResultFields.some(field => field in parsed[0]);
        if (hasToolResultField) {
          return true;
        }
      }
    } catch {
      // 不是有效 JSON，继续检查其他模式
    }
  }
  
  // 如果是 JSON，检查是否包含工具结果的典型字段
  if (looksLikeJson(trimmed)) {
    try {
      const parsed = JSON.parse(trimmed);
      // 检查是否包含工具结果的典型字段
      const toolResultFields = [
        'analysis', 'entities', 'relationships', 'query_intent',
        'relevant_tables', 'table_id', 'relevance_score', 'reasoning',
        'status', 'data', 'error', 'sql', 'result', 'include',
        'likely_aggregations', 'time_related', 'comparison_related'
      ];
      const hasToolResultField = toolResultFields.some(field => field in parsed);
      return hasToolResultField;
    } catch {
      return false;
    }
  }
  
  return false;
}

/**
 * Extracts a string summary from a message's content, supporting multimodal (text, image, file, etc.).
 * - If text is present, returns the joined text.
 * - If not, returns a label for the first non-text modality (e.g., 'Image', 'Other').
 * - If unknown, returns 'Multimodal message'.
 * 
 * 重要：过滤掉工具返回的原始 JSON 数据，避免在 AI 消息中重复显示
 */
export function getContentString(content: Message["content"]): string {
  if (typeof content === "string") {
    // 过滤掉原始 JSON 数据
    if (isToolResultContent(content)) {
      return "";
    }
    return content;
  }
  
  const texts = content
    .filter((c): c is { type: "text"; text: string } => c.type === "text")
    .map((c) => c.text)
    // 过滤掉原始 JSON 数据
    .filter((text) => !isToolResultContent(text));
    
  return texts.join(" ");
}
