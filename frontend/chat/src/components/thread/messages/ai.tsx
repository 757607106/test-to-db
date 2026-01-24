/**
 * AI 消息组件
 * 
 * 基于 LangGraph 官方 streaming 标准实现
 * 
 * @see https://docs.langchain.com/oss/python/langgraph/streaming
 */
import { parsePartialJson } from "@langchain/core/output_parsers";
import { useStreamContext } from "@/providers/Stream";
import { AIMessage, Checkpoint, Message } from "@langchain/langgraph-sdk";
import { getContentString } from "../utils";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { cn } from "@/lib/utils";
import { MessageContentComplex } from "@langchain/core/messages";
import { Fragment, useCallback, useMemo } from "react";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { ThreadView } from "../agent-inbox";
import { useQueryState } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { 
  ClarificationInterruptView, 
  extractClarificationData 
} from "./clarification-interrupt";
import { useArtifact } from "../artifact";
import { QueryPipeline } from "./QueryPipeline";

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
  // 提取澄清数据（支持多种包装格式）
  const clarificationData = extractClarificationData(interrupt);
  const isClarification = clarificationData !== null;
  
  // 通用 fallback 值
  const fallbackValue = Array.isArray(interrupt)
    ? (interrupt as Record<string, any>[])
    : (((interrupt as { value?: unknown } | undefined)?.value ??
        interrupt) as Record<string, any>);

  // 只在最后一条消息或没有 AI 消息时显示 interrupt
  const shouldShow = isLastMessage || hasNoAIOrToolMessages;

  if (!interrupt || !shouldShow) {
    return null;
  }

  return (
    <>
      {/* Agent Inbox 类型的 interrupt */}
      {isAgentInboxInterruptSchema(interrupt) && (
        <ThreadView interrupt={interrupt} />
      )}
      
      {/* 澄清类型的 interrupt - 使用提取后的数据 */}
      {isClarification && clarificationData && (
        <ClarificationInterruptView interrupt={clarificationData} />
      )}
      
      {/* 其他类型的 interrupt */}
      {!isAgentInboxInterruptSchema(interrupt) && !isClarification && (
        <GenericInterruptView interrupt={fallbackValue} />
      )}
    </>
  );
}


function parseAnthropicStreamedToolCalls(
  content: MessageContentComplex[],
): AIMessage["tool_calls"] {
  const toolCallContents = content.filter((c) => c.type === "tool_use" && c.id);

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
      type: "tool_call",
    };
  });
}

export function AssistantMessage({
  message,
  isLoading,
  handleRegenerate,
  connectionId,
}: {
  message: Message | undefined;
  isLoading: boolean;
  handleRegenerate: (parentCheckpoint: Checkpoint | null | undefined) => void;
  connectionId?: number;
}) {
  const content = message?.content ?? [];
  const contentString = getContentString(content);
  const [threadId] = useQueryState("threadId");

  const thread = useStreamContext();
  const isLastMessage =
    thread.messages[thread.messages.length - 1].id === message?.id;
  const hasNoAIOrToolMessages = !thread.messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const meta = message ? thread.getMessagesMetadata(message) : undefined;
  const threadInterrupt = thread.interrupt;

  const toolCalls = message && "tool_calls" in message ? (message as AIMessage).tool_calls : undefined;

  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;
  const anthropicStreamedToolCalls = Array.isArray(content)
    ? parseAnthropicStreamedToolCalls(content)
    : undefined;

  const hasToolCalls =
    message &&
    "tool_calls" in message &&
    message.tool_calls &&
    message.tool_calls.length > 0;
  const hasAnthropicToolCalls = !!anthropicStreamedToolCalls?.length;
  const isToolResult = message?.type === "tool";

  // 准备反馈上下文
  const feedbackContext = useMemo(() => {
    if (!connectionId || !thread.queryContext?.dataQuery) return undefined;
    
    // 获取SQL - 支持新旧节点名称 (sql_executor / final_sql)
    const sqlStep = thread.queryContext.sqlSteps?.find(s => 
      s.step === 'sql_executor' || s.step === 'final_sql'
    );
    const sql = sqlStep?.result || "";
    
    if (!sql) return undefined;

    // 获取问题
    // 简单查找：当前消息之前的最后一个 human message
    let question = "";
    if (message) {
      const msgIndex = thread.messages.findIndex(m => m.id === message.id);
      if (msgIndex > 0) {
        const humanMsg = thread.messages.slice(0, msgIndex).reverse().find(m => m.type === 'human');
        if (humanMsg) {
          question = getContentString(humanMsg.content);
        }
      }
    }

    return {
      question,
      sql,
      connectionId,
      threadId: threadId || undefined
    };
  }, [connectionId, thread.queryContext, thread.messages, message, threadId]);

  const handleSelectQuestion = useCallback((q: string) => {
    const form = document.querySelector("form");
    const textarea = form?.querySelector("textarea") as HTMLTextAreaElement | null;
    if (!textarea || !form) return;
    const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype,
      "value",
    )?.set;
    nativeTextAreaValueSetter?.call(textarea, q);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.focus();
  }, []);

  // 判断是否应该使用 QueryPipeline（优先级高于 ToolCalls）
  // 修复: 只要有 queryContext 数据就显示，不限制 isLastMessage，确保历史消息也能显示工具流
  const hasQueryContextData = thread.queryContext && (
    thread.queryContext.sqlSteps.length > 0 ||
    thread.queryContext.intentAnalysis ||
    thread.queryContext.dataQuery
  );
  const hasAnyToolCalls = hasToolCalls || hasAnthropicToolCalls;
  // 放宽条件：只要有 queryContext 数据就显示，或者是最后一条消息正在执行工具调用
  const useQueryPipeline = hasQueryContextData || (isLastMessage && isLoading && hasAnyToolCalls);

  // 修复: 允许文本内容与工具流共存，消除闪烁
  // 只要有实际文本内容就显示（不再与 QueryPipeline 互斥）
  const shouldShowContent = contentString.trim().length > 0;

  if (isToolResult) {
    // Tool 消息：只显示 Interrupt，ToolResult 组件已移除（返回 null 无实际功能）
    return (
      <div className="group mr-auto flex w-full items-start gap-2">
         <div className="flex w-full flex-col gap-2">
            <Interrupt
              interrupt={threadInterrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
         </div>
      </div>
    );
  }

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        {/* 统一查询流水线 - 优先使用，包含意图解析、SQL步骤、数据、图表、推荐问题 */}
        {useQueryPipeline && thread.queryContext && (
          <QueryPipeline
            queryContext={thread.queryContext}
            onSelectQuestion={handleSelectQuestion}
          />
        )}

        {/* 文本内容 */}
        {shouldShowContent && (
          <div className="py-1">
            <MarkdownText>{contentString}</MarkdownText>
          </div>
        )}

        {/* ToolCalls 组件已移除 - 所有工具调用现在由 QueryPipeline 统一处理 */}
        
        {message && (
          <CustomComponent
            message={message}
            thread={thread}
          />
        )}
        <Interrupt
          interrupt={threadInterrupt}
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
