
import type { Message } from "@langchain/langgraph-sdk";

/**
 * Extracts a string summary from a message's content, supporting multimodal (text, image, file, etc.).
 * - If text is present, returns the joined text.
 * - If not, returns a label for the first non-text modality (e.g., 'Image', 'Other').
 * - If unknown, returns 'Multimodal message'.
 */
export function getContentString(content: Message["content"]): string {
  if (typeof content === "string") {
    // 过滤掉工具返回的JSON结果（不应该显示在消息文本中）
    return filterToolResultJson(content);
  }
  const texts = content
    .filter((c): c is { type: "text"; text: string } => c.type === "text")
    .map((c) => filterToolResultJson(c.text));
  return texts.join(" ").trim();
}

/**
 * 过滤掉工具返回的JSON结果
 * 这些JSON结果应该显示在工具调用的RESULT区域，而不是AI消息文本中
 */
function filterToolResultJson(text: string): string {
  if (!text) return "";
  
  const trimmed = text.trim();
  
  // 检查是否是纯 JSON 对象或数组
  const startsWithJson = trimmed.startsWith("{") || trimmed.startsWith("[");
  const endsWithJson = trimmed.endsWith("}") || trimmed.endsWith("]");
  
  if (startsWithJson && endsWithJson) {
    try {
      const parsed = JSON.parse(trimmed);
      
      // 检查是否是工具返回的特征字段（对象格式）
      if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
        // 检查是否包含analysis字段（这是analyze_user_query工具的返回格式）
        if (parsed.analysis && typeof parsed.analysis === "object") {
          const analysis = parsed.analysis;
          // 如果analysis对象包含entities、relationships、query_intent等字段，则过滤掉
          if (
            (analysis.entities !== undefined && Array.isArray(analysis.entities)) ||
            (analysis.relationships !== undefined && Array.isArray(analysis.relationships)) ||
            (analysis.query_intent !== undefined && typeof analysis.query_intent === "string")
          ) {
            return "";
          }
        }
        
        // 其他工具返回的特征字段
        if (
          parsed.needs_clarification !== undefined ||
          parsed.success !== undefined ||
          parsed.questions !== undefined ||
          parsed.error !== undefined ||
          parsed.analysis !== undefined ||
          parsed.schema_context !== undefined ||
          parsed.value_mappings !== undefined ||
          parsed.entities !== undefined ||
          parsed.relationships !== undefined ||
          parsed.query_intent !== undefined
        ) {
          return "";
        }
      }
      
      // 检查是否是工具返回的数组格式（如 schema 结果）
      if (Array.isArray(parsed) && parsed.length > 0) {
        const firstItem = parsed[0];
        if (typeof firstItem === "object" && firstItem !== null) {
          // 检查是否有工具结果的特征字段
          if (
            firstItem.table_id !== undefined ||
            firstItem.relevance_score !== undefined ||
            firstItem.reasoning !== undefined ||
            firstItem.column_id !== undefined ||
            firstItem.schema_name !== undefined
          ) {
            return "";
          }
        }
      }
    } catch {
      // 不是有效的JSON，保持原样
    }
  }
  
  // 匹配工具返回的JSON结果模式（用于混合内容）
  const toolResultPatterns = [
    // 澄清检查结果
    /\{\s*["']needs_clarification["']\s*:\s*(?:true|false)[^}]*\}/gi,
    // 其他工具返回结果模式
    /\{\s*["']success["']\s*:\s*(?:true|false)[^}]*["']questions["']\s*:\s*\[[^\]]*\][^}]*\}/gi,
    // 匹配以 { "needs_clarification": 开头的完整JSON
    /\{\s*"needs_clarification"\s*:[\s\S]*?"questions"\s*:\s*\[[\s\S]*?\]\s*[,}]/g,
    // 匹配analyze_user_query工具的返回格式（包含analysis字段）- 使用宽松匹配，包括不完整的JSON
    /\{[^}]*["']analysis["'][^}]*["']entities["'][\s\S]*/gi,
  ];
  
  let result = text;
  
  // 移除匹配的JSON
  for (const pattern of toolResultPatterns) {
    result = result.replace(pattern, "").trim();
  }
  
  return result;
}
