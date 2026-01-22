/**
 * AI 消息组件
 * 
 * 基于 LangGraph SDK 官方标准实现
 * 统一渲染 AI 消息和工具消息，简化过滤逻辑
 * 
 * @see https://github.com/langchain-ai/agent-chat-ui
 */
import { parsePartialJson } from "@langchain/core/output_parsers";
import { useStreamContext } from "@/providers/Stream";
import { AIMessage, Checkpoint, Message, ToolMessage } from "@langchain/langgraph-sdk";
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
import { useQueryState, parseAsBoolean } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { ClarificationInterruptView, isClarificationInterrupt } from "./clarification-interrupt";
import { useArtifact } from "../artifact";

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

  return (
    <>
      {/* Agent Inbox 类型的 interrupt */}
      {isAgentInboxInterruptSchema(interrupt) &&
        (isLastMessage || hasNoAIOrToolMessages) && (
          <ThreadView interrupt={interrupt} />
        )}
      
      {/* 澄清类型的 interrupt */}
      {isClarificationInterrupt(interrupt) &&
        (isLastMessage || hasNoAIOrToolMessages) && (
          <ClarificationInterruptView interrupt={interrupt} />
        )}
      
      {/* 其他类型的 interrupt */}
      {interrupt &&
        !isAgentInboxInterruptSchema(interrupt) &&
        !isClarificationInterrupt(interrupt) &&
        (isLastMessage || hasNoAIOrToolMessages) ? (
        <GenericInterruptView interrupt={fallbackValue} />
      ) : null}
    </>
  );
}

/**
 * AI/工具消息组件
 * 
 * 统一处理 AI 消息和工具消息的渲染
 * 简化逻辑：直接基于消息类型渲染对应内容
 */
export function AssistantMessage({
  message,
  isLoading,
  handleRegenerate,
}: {
  message: Message | undefined;
  isLoading: boolean;
  handleRegenerate: (parentCheckpoint: Checkpoint | null | undefined) => void;
}) {
  const [hideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );

  const thread = useStreamContext();
  const messages = Array.isArray(thread.messages) ? thread.messages : [];
  
  // 基础判断
  const isLastMessage = messages.length > 0 && messages[messages.length - 1]?.id === message?.id;
  const hasNoAIOrToolMessages = !messages.find((m) => m.type === "ai" || m.type === "tool");
  const meta = message ? thread.getMessagesMetadata(message) : undefined;
  const threadInterrupt = thread.interrupt;
  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;

  // 消息内容处理
  const content = message?.content ?? [];
  const contentString = getContentString(content);
  
  // 工具调用检测 - 简化逻辑
  const isToolResult = message?.type === "tool";
  const hasToolCalls = message && "tool_calls" in message && Array.isArray(message.tool_calls) && message.tool_calls.length > 0;
  
  // Anthropic 流式工具调用解析
  const anthropicStreamedToolCalls = Array.isArray(content)
    ? parseAnthropicStreamedToolCalls(content as MessageContentComplex[])
    : undefined;
  const hasAnthropicToolCalls = anthropicStreamedToolCalls && anthropicStreamedToolCalls.length > 0;

  // 如果隐藏工具调用且是工具结果，不渲染
  if (isToolResult && hideToolCalls) {
    return null;
  }

  // 渲染工具结果消息
  if (isToolResult) {
    return (
      <div className="group mr-auto flex w-full items-start gap-2">
        <div className="flex w-full flex-col gap-2">
          <ToolResult message={message as ToolMessage} />
          <Interrupt
            interrupt={threadInterrupt}
            isLastMessage={isLastMessage}
            hasNoAIOrToolMessages={hasNoAIOrToolMessages}
          />
        </div>
      </div>
    );
  }

  // 渲染 AI 消息
  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        {/* 文本内容 */}
        {contentString.length > 0 && (
          <div className="py-1">
            <MarkdownText>{contentString}</MarkdownText>
          </div>
        )}

        {/* 工具调用显示 - 简化条件判断 */}
        {!hideToolCalls && (hasToolCalls || hasAnthropicToolCalls) && (
          <ToolCalls 
            toolCalls={hasToolCalls ? (message as AIMessage).tool_calls : anthropicStreamedToolCalls} 
          />
        )}

        {/* 自定义组件 */}
        {message && (
          <CustomComponent message={message} thread={thread} />
        )}

        {/* 中断处理 */}
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
          />
        </div>
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
