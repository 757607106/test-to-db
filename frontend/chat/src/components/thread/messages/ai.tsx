/**
 * AI 消息组件
 * 
 * 直接参考 LangChain agent-chat-ui 官方实现
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
import { MessageContentComplex } from "@langchain/core/messages";
import { Fragment, useCallback, useMemo } from "react";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { ThreadView } from "../agent-inbox";
import { useQueryState, parseAsBoolean } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { 
  ClarificationInterruptView, 
  extractClarificationData 
} from "./clarification-interrupt";
import { useArtifact } from "../artifact";
import { ToolCalls, ToolResult } from "./tool-calls";
import { DataChartDisplay } from "./DataChartDisplay";
import { Sparkles } from "lucide-react";

/**
 * 推荐问题组件
 */
function SimilarQuestions({ 
  questions,
  onSelectQuestion 
}: { 
  questions: string[];
  onSelectQuestion?: (question: string) => void;
}) {
  if (!questions || questions.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
      <div className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-50 to-pink-50 border-b border-slate-200">
        <Sparkles className="h-4 w-4 text-purple-600" />
        <span className="font-medium text-sm text-slate-700">您可能还想问</span>
      </div>
      <div className="p-4 space-y-2">
        {questions.map((question, index) => (
          <button
            key={index}
            onClick={() => onSelectQuestion?.(question)}
            className="w-full text-left px-4 py-2.5 rounded-lg bg-slate-50 hover:bg-purple-50 border border-slate-200 hover:border-purple-200 transition-colors group"
          >
            <span className="text-sm text-slate-700 group-hover:text-purple-700">
              {question}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
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
  const clarificationData = extractClarificationData(interrupt);
  const isClarification = clarificationData !== null;
  
  const fallbackValue = Array.isArray(interrupt)
    ? (interrupt as Record<string, any>[])
    : (((interrupt as { value?: unknown } | undefined)?.value ??
        interrupt) as Record<string, any>);

  return (
    <>
      {isAgentInboxInterruptSchema(interrupt) &&
        (isLastMessage || hasNoAIOrToolMessages) && (
          <ThreadView interrupt={interrupt} />
        )}
      {isClarification && clarificationData && (isLastMessage || hasNoAIOrToolMessages) && (
        <ClarificationInterruptView interrupt={clarificationData} />
      )}
      {interrupt &&
      !isAgentInboxInterruptSchema(interrupt) &&
      !isClarification &&
      (isLastMessage || hasNoAIOrToolMessages) ? (
        <GenericInterruptView interrupt={fallbackValue} />
      ) : null}
    </>
  );
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
  
  // 和官方一样，默认显示工具调用 (false)
  const [hideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  const [threadId] = useQueryState("threadId");

  const thread = useStreamContext();
  const isLastMessage =
    thread.messages[thread.messages.length - 1].id === message?.id;
  const hasNoAIOrToolMessages = !thread.messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const meta = message ? thread.getMessagesMetadata(message) : undefined;
  const threadInterrupt = thread.interrupt;

  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;
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

  // 数据可视化相关
  const hasQueryData = isLastMessage && thread.queryContext?.dataQuery;
  const hasChartConfig = hasQueryData && thread.queryContext?.dataQuery?.chart_config;
  const hasSimilarQuestions = isLastMessage && 
    thread.queryContext?.similarQuestions?.questions && 
    thread.queryContext.similarQuestions.questions.length > 0;

  // 反馈上下文
  const feedbackContext = useMemo(() => {
    if (!connectionId || !thread.queryContext?.dataQuery) return undefined;
    const sqlStep = thread.queryContext.sqlSteps?.find(s => 
      s.step === 'sql_executor' || s.step === 'final_sql'
    );
    const sql = sqlStep?.result || "";
    if (!sql) return undefined;

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

    return { question, sql, connectionId, threadId: threadId || undefined };
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
    
    // 自动提交表单，触发新的查询
    setTimeout(() => {
      form.requestSubmit();
    }, 50);
  }, []);

  // Tool 消息处理 - 和官方一样
  if (isToolResult && hideToolCalls) {
    return null;
  }

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        {isToolResult ? (
          <>
            <ToolResult message={message} />
            <Interrupt
              interrupt={threadInterrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
          </>
        ) : (
          <>
            {/* 流式文字内容 */}
            {contentString.length > 0 && (
              <div className="py-1">
                <MarkdownText>{contentString}</MarkdownText>
              </div>
            )}

            {/* 工具调用 - 和官方一样 */}
            {!hideToolCalls && (
              <>
                {(hasToolCalls && toolCallsHaveContents && (
                  <ToolCalls toolCalls={message.tool_calls} />
                )) ||
                  (hasAnthropicToolCalls && (
                    <ToolCalls toolCalls={anthropicStreamedToolCalls} />
                  )) ||
                  (hasToolCalls && (
                    <ToolCalls toolCalls={message.tool_calls} />
                  ))}
              </>
            )}

            {/* 数据可视化图表 */}
            {hasChartConfig && thread.queryContext?.dataQuery && (
              <DataChartDisplay dataQuery={thread.queryContext.dataQuery} />
            )}

            {/* 推荐问题 */}
            {hasSimilarQuestions && thread.queryContext?.similarQuestions && (
              <SimilarQuestions 
                questions={thread.queryContext.similarQuestions.questions}
                onSelectQuestion={handleSelectQuestion}
              />
            )}

            {/* 自定义组件 */}
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
