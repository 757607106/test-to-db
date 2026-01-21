/**
 * AI 消息组件
 * 
 * 基于官方 agent-chat-ui 实现，原生支持 Tool 工具调用显示
 * @see https://github.com/langchain-ai/agent-chat-ui
 */
import { parsePartialJson } from "@langchain/core/output_parsers";
import { useStreamContext } from "@/providers/Stream";
import { AIMessage, Checkpoint, Message } from "@langchain/langgraph-sdk";
import { getContentString } from "../utils";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { cn } from "@/lib/utils";
import { ToolCalls, ToolResult } from "./tool-calls";
import { MessageContentComplex } from "@langchain/core/messages";
import { Fragment } from "react/jsx-runtime";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { ThreadView } from "../agent-inbox";
import { useQueryState, parseAsBoolean, parseAsInteger } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { ClarificationInterruptView, isClarificationInterrupt } from "./clarification-interrupt";
import { useArtifact } from "../artifact";
import { useMemo } from "react";

// 反馈服务类型定义（保留自定义功能）
export interface FeedbackContext {
  question: string;      // 用户的原始问题
  sql: string;          // 生成的SQL语句
  connectionId: number; // 数据库连接ID
  threadId?: string;    // 会话线程ID（可选）
}

/**
 * 从AI消息内容中提取SQL语句
 */
function extractSQLFromContent(content: string): string | null {
  if (!content || typeof content !== 'string') {
    return null;
  }

  // 尝试匹配 ```sql ... ``` 格式
  const sqlBlockMatch = content.match(/```sql\s*([\s\S]*?)\s*```/i);
  if (sqlBlockMatch && sqlBlockMatch[1]) {
    return sqlBlockMatch[1].trim();
  }

  // 尝试匹配以 SELECT/INSERT/UPDATE/DELETE 开头的SQL
  const sqlMatch = content.match(/\b(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|DROP|ALTER)\b[\s\S]+?;/i);
  if (sqlMatch) {
    return sqlMatch[0].trim();
  }

  return null;
}

function CustomComponent({
  message,
  thread,
}: {
  message: Message;
  thread: ReturnType<typeof useStreamContext>;
}) {
  const artifact = useArtifact();
  const { values } = useStreamContext();
  const customComponents = values.ui?.filter(
    (ui) => ui.metadata?.message_id === message.id,
  );

  if (!customComponents?.length) return null;
  return (
    <Fragment key={message.id}>
      {customComponents.map((customComponent) => (
        <LoadExternalComponent
          key={customComponent.id}
          stream={thread}
          message={customComponent}
          meta={{ ui: customComponent, artifact }}
        />
      ))}
    </Fragment>
  );
}

/**
 * 解析 Anthropic 流式工具调用（官方实现）
 */
function parseAnthropicStreamedToolCalls(
  content: MessageContentComplex[],
): AIMessage["tool_calls"] {
  const toolCallContents = content.filter((c) => c.type === "tool_use" && (c as any).id);

  return toolCallContents.map((tc) => {
    const toolCall = tc as Record<string, any>;
    let json: Record<string, any> = {};
    if (toolCall?.input) {
      try {
        json = parsePartialJson(toolCall.input) ?? {};
      } catch {
        // Pass
      }
    }
    return {
      name: toolCall.name ?? "",
      id: toolCall.id ?? "",
      args: json,
      type: "tool_call" as const,
    };
  });
}

interface InterruptProps {
  interrupt?: unknown;
  isLastMessage: boolean;
  hasNoAIOrToolMessages: boolean;
}

function Interrupt({
  interrupt,
  isLastMessage,
  hasNoAIOrToolMessages,
}: InterruptProps) {
  const fallbackValue = Array.isArray(interrupt)
    ? (interrupt as Record<string, any>[])
    : (((interrupt as { value?: unknown } | undefined)?.value ??
        interrupt) as Record<string, any>);

  const shouldShow = isLastMessage || hasNoAIOrToolMessages;
  if (!shouldShow || !interrupt) return null;

  return (
    <>
      {/* Agent Inbox 类型的 interrupt */}
      {isAgentInboxInterruptSchema(interrupt) && (
        <ThreadView interrupt={interrupt} />
      )}
      
      {/* 澄清类型的 interrupt - 使用专门的澄清组件 */}
      {isClarificationInterrupt(interrupt) && (
        <ClarificationInterruptView interrupt={interrupt} />
      )}
      
      {/* 其他类型的 interrupt - 使用通用组件 */}
      {!isAgentInboxInterruptSchema(interrupt) &&
       !isClarificationInterrupt(interrupt) && (
        <GenericInterruptView interrupt={fallbackValue} />
      )}
    </>
  );
}

export function AssistantMessage({
  message,
  isLoading,
  handleRegenerate,
}: {
  message: Message | undefined;
  isLoading: boolean;
  handleRegenerate: (parentCheckpoint: Checkpoint | null | undefined) => void;
}) {
  const content = message?.content ?? [];
  const contentString = getContentString(content);
  
  const [hideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  // 获取连接ID（从URL参数，与用户选择的数据库连接同步）
  const [connectionId] = useQueryState(
    "connectionId",
    parseAsInteger.withDefault(0),
  );
  // 获取线程ID
  const [threadId] = useQueryState("threadId");

  const thread = useStreamContext();
  const messages = Array.isArray(thread.messages) ? thread.messages : [];
  const isLastMessage =
    messages.length > 0 && messages[messages.length - 1]?.id === message?.id;
  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const meta = message ? thread.getMessagesMetadata(message) : undefined;
  const threadInterrupt = thread.interrupt;

  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;
  
  // 解析 Anthropic 流式工具调用
  const anthropicStreamedToolCalls = Array.isArray(content)
    ? parseAnthropicStreamedToolCalls(content as MessageContentComplex[])
    : undefined;

  // 工具调用相关判断（官方逻辑）
  const hasToolCalls =
    message &&
    "tool_calls" in message &&
    message.tool_calls &&
    message.tool_calls.length > 0;
  const toolCallsHaveContents =
    hasToolCalls &&
    (message as AIMessage).tool_calls?.some(
      (tc) => tc.args && Object.keys(tc.args).length > 0,
    );
  const hasAnthropicToolCalls = !!anthropicStreamedToolCalls?.length;
  const isToolResult = message?.type === "tool";

  // 计算工具调用状态：检查是否有对应的 tool result
  const toolCallStatus = useMemo(() => {
    if (!hasToolCalls && !hasAnthropicToolCalls) return "complete";
    
    const currentToolCalls = hasToolCalls 
      ? (message as AIMessage).tool_calls 
      : anthropicStreamedToolCalls;
    
    if (!currentToolCalls || currentToolCalls.length === 0) return "complete";
    
    // 检查是否所有工具调用都有对应的结果
    const toolCallIds = currentToolCalls.map(tc => tc.id).filter(Boolean);
    const messageIndex = messages.findIndex((m) => m.id === message?.id);
    
    // 查找当前消息之后的 tool 类型消息
    const subsequentToolResults = messages
      .slice(messageIndex + 1)
      .filter(m => m.type === "tool")
      .map(m => (m as any).tool_call_id);
    
    // 如果所有工具调用都有对应结果，则为完成状态
    const allComplete = toolCallIds.every(id => subsequentToolResults.includes(id));
    
    return allComplete ? "complete" : "running";
  }, [hasToolCalls, hasAnthropicToolCalls, message, messages, anthropicStreamedToolCalls]) as "running" | "complete" | "error";

  // 构建反馈上下文（用于点赞/点踩功能）
  const feedbackContext = useMemo<FeedbackContext | undefined>(() => {
    // 提取SQL
    const sql = extractSQLFromContent(contentString);
    if (!sql) return undefined;

    // 必须有有效的连接ID
    if (!connectionId || connectionId <= 0) {
      return undefined;
    }

    // 查找对应的用户问题（查找当前AI消息之前最近的human消息）
    const messageIndex = messages.findIndex((m) => m.id === message?.id);
    let userQuestion = '';
    
    if (messageIndex > 0) {
      // 向前查找最近的human消息
      for (let i = messageIndex - 1; i >= 0; i--) {
        const msg = messages[i];
        if (msg.type === 'human') {
          userQuestion = getContentString(msg.content);
          break;
        }
      }
    }
    
    if (!userQuestion) return undefined;

    return {
      question: userQuestion,
      sql: sql,
      connectionId: connectionId,
      threadId: threadId ?? undefined,
    };
  }, [contentString, messages, message?.id, connectionId, threadId]);

  // 隐藏工具调用时，不渲染 tool 类型的消息
  if (isToolResult && hideToolCalls) {
    return null;
  }

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        {isToolResult ? (
          // 工具结果消息 - 使用官方 ToolResult 组件
          <>
            <ToolResult message={message} />
            <Interrupt
              interrupt={threadInterrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
          </>
        ) : (
          // AI 消息
          <>
            {/* 消息内容 */}
            {contentString.length > 0 && (
              <div className="py-1">
                <MarkdownText>{contentString}</MarkdownText>
              </div>
            )}

            {/* 工具调用 - 使用官方 ToolCalls 组件 */}
            {!hideToolCalls && (
              <>
                {(hasToolCalls && toolCallsHaveContents && (
                  <ToolCalls toolCalls={(message as AIMessage).tool_calls} status={toolCallStatus} />
                )) ||
                  (hasAnthropicToolCalls && (
                    <ToolCalls toolCalls={anthropicStreamedToolCalls} status={toolCallStatus} />
                  )) ||
                  (hasToolCalls && (
                    <ToolCalls toolCalls={(message as AIMessage).tool_calls} status={toolCallStatus} />
                  ))}
              </>
            )}

            {/* 自定义组件 */}
            {message && (
              <CustomComponent
                message={message}
                thread={thread}
              />
            )}
            
            {/* Interrupt 处理 */}
            <Interrupt
              interrupt={threadInterrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
            
            {/* 操作栏 */}
            <div
              className={cn(
                "mr-auto flex items-center gap-2 transition-opacity",
                "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100",
              )}
            >
              <BranchSwitcher
                branch={meta?.branch}
                branchOptions={meta?.branchOptions}
                onSelect={(branch) => thread.setBranch(branch)}
                isLoading={isLoading}
              />
              <CommandBar
                content={contentString}
                isLoading={isLoading}
                isAiMessage={true}
                handleRegenerate={() => handleRegenerate(parentCheckpoint)}
                feedbackContext={feedbackContext}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function AssistantMessageLoading() {
  return (
    <div className="mr-auto flex items-start gap-2">
      <div className="bg-muted flex h-8 items-center gap-1 rounded-2xl px-4 py-2">
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_0.5s_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_1s_infinite] rounded-full"></div>
      </div>
    </div>
  );
}
