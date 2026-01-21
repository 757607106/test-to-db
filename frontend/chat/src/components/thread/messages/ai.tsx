import { parsePartialJson } from "@langchain/core/output_parsers";
import { useStreamContext } from "@/providers/Stream";
import { AIMessage, Checkpoint, Message, ToolMessage } from "@langchain/langgraph-sdk";
import { getContentString } from "../utils";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { cn } from "@/lib/utils";
import { ToolCalls } from "./tool-calls";
import { MessageContentComplex } from "@langchain/core/messages";
import { Fragment } from "react/jsx-runtime";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { ThreadView } from "../agent-inbox";
import { useQueryState, parseAsBoolean, parseAsInteger } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { ClarificationInterruptView, isClarificationInterrupt } from "./clarification-interrupt";
import { useArtifact } from "../artifact";
import { useMemo } from "react";

// 反馈服务类型定义
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

/**
 * Check if a tool call ID matches a tool result's tool_call_id
 * ✅ 简化版本：后端已通过 generate_tool_call_id() 确保 ID 不重复
 */
function toolCallIdMatches(toolCallId: string, toolResultId: string): boolean {
  return toolCallId === toolResultId;
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

function parseAnthropicStreamedToolCalls(
  content: MessageContentComplex[],
): AIMessage["tool_calls"] {
  const toolCallContents = content.filter((c) => c.type === "tool_use" && c.id);

  return toolCallContents
    .map((tc) => {
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
    // ✅ 移除空 name 过滤：后端已通过 create_ai_message_with_tools() 确保 name 非空
}

interface InterruptProps {
  interruptValue?: unknown;
  isLastMessage: boolean;
  hasNoAIOrToolMessages: boolean;
}

function Interrupt({
  interruptValue,
  isLastMessage,
  hasNoAIOrToolMessages,
}: InterruptProps) {
  // 只在最后一条消息或没有AI/Tool消息时显示interrupt
  const shouldShow = isLastMessage || hasNoAIOrToolMessages;
  
  if (!shouldShow || !interruptValue) {
    return null;
  }
  
  return (
    <>
      {/* Agent Inbox 类型的 interrupt */}
      {isAgentInboxInterruptSchema(interruptValue) && (
        <ThreadView interrupt={interruptValue} />
      )}
      
      {/* 澄清类型的 interrupt - 使用专门的澄清组件 */}
      {isClarificationInterrupt(interruptValue) && (
        <ClarificationInterruptView interrupt={interruptValue} />
      )}
      
      {/* 其他类型的 interrupt - 使用通用组件 */}
      {!isAgentInboxInterruptSchema(interruptValue) &&
       !isClarificationInterrupt(interruptValue) && (
        <GenericInterruptView interrupt={interruptValue} />
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
    messages.length > 0 && messages[messages.length - 1].id === message?.id;
  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const meta = message ? thread.getMessagesMetadata(message) : undefined;
  const threadInterrupt = thread.interrupt;

  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;

  // 构建反馈上下文（用于点赞/点踩功能）
  const feedbackContext = useMemo<FeedbackContext | undefined>(() => {
    // 提取SQL
    const sql = extractSQLFromContent(contentString);
    if (!sql) return undefined;

    // 必须有有效的连接ID
    if (!connectionId || connectionId <= 0) {
      console.log('[FeedbackContext] 无有效的连接ID，跳过反馈功能');
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

    console.log('[FeedbackContext] 构建反馈上下文:', {
      connectionId,
      hasSQL: !!sql,
      hasQuestion: !!userQuestion,
      threadId: threadId
    });

    return {
      question: userQuestion,
      sql: sql,
      connectionId: connectionId,
      threadId: threadId ?? undefined,
    };
  }, [contentString, messages, message?.id, connectionId, threadId]);
  const anthropicStreamedToolCalls = Array.isArray(content)
    ? parseAnthropicStreamedToolCalls(content)
    : undefined;

  const hasToolCalls =
    message &&
    "tool_calls" in message &&
    message.tool_calls &&
    message.tool_calls.length > 0;
  const toolCallsHaveContents =
    hasToolCalls &&
    message.tool_calls?.some(
      (tc) => tc.args && Object.keys(tc.args).length > 0,
    );
  const hasAnthropicToolCalls = !!anthropicStreamedToolCalls?.length;
  const isToolResult = message?.type === "tool";

  if (isToolResult) {
    return null; // Hide individual tool results since they're now combined with tool calls
  }

  return (
    <div className="group mr-auto w-full">
      <div className="flex flex-col gap-2">
        {!isToolResult && (
          <>
            {contentString.length > 0 && (
              <div className="py-1">
                <MarkdownText>{contentString}</MarkdownText>
              </div>
            )}

            {!hideToolCalls && (
              <>
                {(hasToolCalls && toolCallsHaveContents && (
                  <ToolCalls
                    toolCalls={message.tool_calls}
                    toolResults={messages.filter(
                      (m): m is ToolMessage =>
                        m.type === "tool" &&
                        !!message.tool_calls?.some(tc => toolCallIdMatches(tc.id || "", (m as any).tool_call_id || ""))
                    )}
                  />
                )) ||
                  (hasAnthropicToolCalls && (
                    <ToolCalls
                      toolCalls={anthropicStreamedToolCalls}
                      toolResults={messages.filter(
                        (m): m is ToolMessage =>
                          m.type === "tool" &&
                          anthropicStreamedToolCalls?.some(tc => toolCallIdMatches(tc.id || "", (m as any).tool_call_id || ""))
                      )}
                    />
                  )) ||
                  (hasToolCalls && (
                    <ToolCalls
                      toolCalls={message.tool_calls}
                      toolResults={messages.filter(
                        (m): m is ToolMessage =>
                          m.type === "tool" &&
                          !!message.tool_calls?.some(tc => toolCallIdMatches(tc.id || "", (m as any).tool_call_id || ""))
                      )}
                    />
                  ))}
              </>
            )}

            {message && (
              <CustomComponent
                message={message}
                thread={thread}
              />
            )}
            <Interrupt
              interruptValue={threadInterrupt?.value}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
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
