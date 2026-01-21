/**
 * Agent消息统一格式类型定义
 * 
 * 与后端 backend/app/schemas/agent_message.py 中的 ToolResponse 保持一致
 * 确保前后端类型安全
 */

/**
 * 工具执行结果的统一格式
 * 
 * 所有Agent工具返回的结果都遵循此格式，简化前端解析逻辑
 */
export interface ToolResponse {
  /**
   * 执行状态
   * - success: 执行成功
   * - error: 执行失败
   * - pending: 等待执行或执行中
   */
  status: "success" | "error" | "pending";
  
  /**
   * 成功时的数据负载
   * 可以是任意类型的数据（SQL结果、图表配置、样本数据等）
   */
  data?: any;
  
  /**
   * 错误信息（仅当 status="error" 时存在）
   */
  error?: string;
  
  /**
   * 附加元数据
   * 如：execution_time, cache_info, row_count 等
   */
  metadata?: Record<string, any>;
}

/**
 * 解析工具执行结果
 * 
 * 统一的解析函数，处理可能的字符串或对象格式
 * 
 * @param content - 工具返回的内容（可能是字符串或对象）
 * @returns 解析后的 ToolResponse 对象
 * 
 * @example
 * ```typescript
 * // 解析字符串格式
 * const result = parseToolResult('{"status":"success","data":{"rows":[...]}}');
 * console.log(result.status); // "success"
 * 
 * // 解析对象格式
 * const result2 = parseToolResult({status: "success", data: {...}});
 * console.log(result2.data); // {...}
 * ```
 */
export function parseToolResult(content: string | any): ToolResponse {
  // 如果已经是对象，直接返回
  if (typeof content !== "string") {
    return content as ToolResponse;
  }
  
  // 如果是字符串，尝试解析为JSON
  try {
    const parsed = JSON.parse(content);
    return parsed as ToolResponse;
  } catch (error) {
    // JSON 解析失败，判断是否为成功的纯文本消息
    const lowerContent = content.toLowerCase();
    const isSuccessMessage = 
      lowerContent.includes("success") ||
      lowerContent.includes("transferred") ||
      lowerContent.includes("completed") ||
      lowerContent.includes("done");
    
    if (isSuccessMessage) {
      // 成功的纯文本消息
      return {
        status: "success",
        data: { message: content }
      };
    } else {
      // 其他情况视为错误
      console.warn("Failed to parse tool result as JSON:", content);
      return {
        status: "error",
        error: "Failed to parse tool result",
        data: content
      };
    }
  }
}

/**
 * 向后兼容的解析函数
 * 
 * 在迁移期间支持旧格式（{success: boolean}）和新格式（{status: string}）
 * 
 * @param content - 工具返回的内容
 * @returns 解析后的 ToolResponse 对象
 * 
 * @deprecated 迁移完成后应使用 parseToolResult
 */
export function parseToolResultCompat(content: string | any): ToolResponse {
  const parsed = typeof content === "string" ? JSON.parse(content) : content;
  
  // 新格式（有 status 字段）
  if (parsed.status) {
    return parsed as ToolResponse;
  }
  
  // 旧格式（有 success 字段）- 转换为新格式
  if (parsed.success !== undefined) {
    return {
      status: parsed.success ? "success" : "error",
      data: parsed.data,
      error: parsed.error,
      metadata: {
        // 保留旧格式的其他字段作为 metadata
        ...(parsed.execution_time && { execution_time: parsed.execution_time }),
        ...(parsed.rows_affected && { rows_affected: parsed.rows_affected }),
        ...(parsed.from_cache && { from_cache: parsed.from_cache })
      }
    };
  }
  
  // 未知格式，返回错误
  return {
    status: "error",
    error: "Unknown tool response format",
    data: parsed
  };
}

/**
 * 检查工具结果是否为错误
 * 
 * @param result - ToolResponse 对象
 * @returns 是否为错误状态
 */
export function isToolError(result: ToolResponse | null | undefined): boolean {
  return result?.status === "error";
}

/**
 * 检查工具结果是否成功
 * 
 * @param result - ToolResponse 对象
 * @returns 是否为成功状态
 */
export function isToolSuccess(result: ToolResponse | null | undefined): boolean {
  return result?.status === "success";
}

/**
 * 检查工具结果是否待处理
 * 
 * @param result - ToolResponse 对象
 * @returns 是否为待处理状态
 */
export function isToolPending(result: ToolResponse | null | undefined): boolean {
  return result?.status === "pending";
}
