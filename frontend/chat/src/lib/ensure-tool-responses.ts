/**
 * 工具调用响应处理
 * 
 * 基于 LangGraph SDK 官方标准实现
 * 确保每个 tool_call 都有对应的 ToolMessage
 * 
 * @see https://github.com/langchain-ai/agent-chat-ui
 */
import { v4 as uuidv4 } from "uuid";
import { Message, ToolMessage } from "@langchain/langgraph-sdk";

/** 不需要渲染的消息 ID 前缀 */
export const DO_NOT_RENDER_ID_PREFIX = "do-not-render-";

/**
 * 确保所有工具调用都有对应的响应消息
 * 
 * LangGraph 要求每个 AIMessage 中的 tool_call 都必须有
 * 一个对应的 ToolMessage 响应，否则会出错。
 * 
 * 此函数检查消息列表，为缺失响应的工具调用创建占位消息。
 * 
 * @param messages - 消息列表
 * @returns 需要添加的占位 ToolMessage 列表
 */
export function ensureToolCallsHaveResponses(messages: Message[]): ToolMessage[] {
  if (!Array.isArray(messages) || messages.length === 0) {
    return [];
  }

  const newMessages: ToolMessage[] = [];
  
  // 收集所有已存在的 tool_call_id
  const existingToolCallIds = new Set<string>();
  messages.forEach((msg) => {
    if (msg.type === "tool" && msg.tool_call_id) {
      existingToolCallIds.add(msg.tool_call_id);
    }
  });

  // 检查每个 AI 消息的工具调用
  messages.forEach((message) => {
    // 只处理有工具调用的 AI 消息
    if (message.type !== "ai" || !message.tool_calls?.length) {
      return;
    }

    // 为每个缺失响应的工具调用创建占位消息
    message.tool_calls.forEach((tc) => {
      const toolCallId = tc.id ?? "";
      
      // 如果已经有对应的 ToolMessage，跳过
      if (existingToolCallIds.has(toolCallId)) {
        return;
      }

      // 创建占位 ToolMessage
      newMessages.push({
        type: "tool" as const,
        tool_call_id: toolCallId,
        id: `${DO_NOT_RENDER_ID_PREFIX}${uuidv4()}`,
        name: tc.name ?? "unknown",
        content: JSON.stringify({
          status: "pending",
          message: "Tool call in progress..."
        }),
      } as ToolMessage);
    });
  });

  return newMessages;
}

/**
 * 确保所有 ToolMessage 都有对应的父 AI 消息
 * 修复 "messages with role 'tool' must be a response to a preceeding message with 'tool_calls'" 错误
 */
export function ensureOrphanedToolMessagesHaveParents(messages: Message[]): Message[] {
  if (!Array.isArray(messages) || messages.length === 0) {
    return [];
  }

  const newMessages: Message[] = [];
  const existingToolCallIdsInAI = new Set<string>();

  // 收集所有 AI 消息引用的 tool_call_id
  messages.forEach((msg) => {
    if (msg.type === "ai" && msg.tool_calls) {
      msg.tool_calls.forEach((tc) => {
        if (tc.id) existingToolCallIdsInAI.add(tc.id);
      });
    }
  });

  // 检查每个 ToolMessage
  messages.forEach((msg) => {
    if (msg.type === "tool" && msg.tool_call_id) {
      if (!existingToolCallIdsInAI.has(msg.tool_call_id)) {
        // 发现孤立的 ToolMessage，创建一个虚拟的父 AI 消息
        newMessages.push({
          type: "ai",
          id: `${DO_NOT_RENDER_ID_PREFIX}fix-${uuidv4()}`,
          content: "",
          tool_calls: [
            {
              name: msg.name || "unknown",
              args: {},
              id: msg.tool_call_id,
            }
          ]
        } as unknown as Message);
      }
    }
  });

  return newMessages;
}

/**
 * 检查消息是否是占位消息（不应该渲染）
 */
export function isPlaceholderMessage(message: Message): boolean {
  return message.id?.startsWith(DO_NOT_RENDER_ID_PREFIX) ?? false;
}
