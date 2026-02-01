/**
 * AI 消息组件
 * 
 * 直接参考 LangChain agent-chat-ui 官方实现
 * @see https://github.com/langchain-ai/agent-chat-ui
 */
import { useStreamContext } from "@/providers/Stream";
import { Checkpoint, Message } from "@langchain/langgraph-sdk";
import { getContentString } from "../utils";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { cn } from "@/lib/utils";
import { Fragment, useCallback, useMemo, memo } from "react";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { DO_NOT_RENDER_ID_PREFIX } from "@/lib/ensure-tool-responses";
import { ThreadView } from "../agent-inbox";
import { useQueryState } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { 
  ClarificationInterruptView, 
  extractClarificationData 
} from "./clarification-interrupt";
import { useArtifact } from "../artifact";
import { ToolCall } from "@langchain/core/messages/tool";
import { ToolCallTable } from "../agent-inbox/components/tool-call-table";
import { DataChartDisplay } from "./DataChartDisplay";
import { InsightDisplay } from "./InsightDisplay";
import {
  Sparkles,
} from "lucide-react";
import { SQL_STEP_LABELS } from "@/types/stream-events";

/**
 * 推荐问题组件 - 使用 memo 优化
 */
const SimilarQuestions = memo(function SimilarQuestions({ 
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
});

function formatDuration(ms: number | undefined) {
  if (ms == null) return "";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

export function StageMessageBubble({
  message,
  step,
  timeMs,
}: {
  message: string;
  step?: string;
  timeMs?: number;
}) {
  const label = step ? SQL_STEP_LABELS[step] ?? step : "阶段消息";
  const duration = formatDuration(timeMs);

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        <div className="rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 overflow-hidden shadow-sm">
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/40">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
              {label}
            </span>
            {duration && (
              <span className="text-xs text-slate-400">{duration}</span>
            )}
          </div>
          <div className="px-3 py-2">
            <pre className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap break-words">
              {message}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

function getToolContentString(content: Message["content"]): string {
  if (typeof content === "string") return content;
  if (!content || !Array.isArray(content)) return "";
  return content
    .map((c) => {
      if (typeof c === "string") return c;
      if (c && typeof c === "object" && "type" in c) {
        const candidate = c as { type?: string; text?: string };
        if (candidate.type === "text" && typeof candidate.text === "string") {
          return candidate.text;
        }
      }
      return "";
    })
    .filter(Boolean)
    .join(" ");
}

function ToolMessageBubble({ message }: { message: Message }) {
  const toolName = (message as { name?: string }).name ?? "tool";
  const toolCallId = (message as { tool_call_id?: string }).tool_call_id;
  const rawContent = getToolContentString(message.content);
  let formattedContent = rawContent;
  let status: string | undefined;
  let summary: string | undefined;

  if (rawContent) {
    try {
      const parsed = JSON.parse(rawContent) as Record<string, unknown>;
      formattedContent = JSON.stringify(parsed, null, 2);
      if (typeof parsed?.status === "string") {
        status = parsed.status;
      }
      if (typeof parsed?.message === "string") {
        summary = parsed.message;
      } else if (typeof parsed?.error === "string") {
        summary = parsed.error;
      }
    } catch {
      formattedContent = rawContent;
    }
  }

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        <div className="rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 overflow-hidden shadow-sm">
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/40">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
              {toolCallId ? `${toolName} #${toolCallId.slice(0, 8)}` : toolName}
            </span>
            {status && (
              <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
                {status}
              </span>
            )}
          </div>
          <div className="px-3 py-2 space-y-2">
            {summary && (
              <div className="text-xs text-slate-500 dark:text-slate-400">
                {summary}
              </div>
            )}
            {formattedContent && (
              <pre className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap break-words">
                {formattedContent}
              </pre>
            )}
          </div>
        </div>
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
  const [threadId] = useQueryState("threadId");

  const thread = useStreamContext();
  
  // 性能优化：避免每次都复制和反转整个消息数组
  const lastRenderableMessageId = useMemo(() => {
    // 从后向前查找，不需要复制数组
    for (let i = thread.messages.length - 1; i >= 0; i--) {
      const m = thread.messages[i];
      if (m.type !== "tool" && !m.id?.startsWith(DO_NOT_RENDER_ID_PREFIX)) {
        return m.id;
      }
    }
    return undefined;
  }, [thread.messages]);
  
  const isLastMessage = lastRenderableMessageId === message?.id;
  const hasNoAIOrToolMessages = !thread.messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const meta = message ? thread.getMessagesMetadata(message) : undefined;
  const threadInterrupt = thread.interrupt;

  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;
  const isToolResult = message?.type === "tool";
  const toolCalls =
    message && "tool_calls" in message && Array.isArray(message.tool_calls)
      ? (message.tool_calls as ToolCall[])
      : [];

  const hasQueryData = thread.queryContext?.dataQuery;
  const hasChartConfig = hasQueryData && thread.queryContext?.dataQuery?.chart_config;
  const hasSimilarQuestions = thread.queryContext?.similarQuestions?.questions && 
    thread.queryContext.similarQuestions.questions.length > 0;
  const hasInsight = thread.queryContext?.insight && 
    (thread.queryContext.insight.summary || thread.queryContext.insight.insights.length > 0);
  // 只有当消息是最后一条消息时，才关联全局的 queryContext
  // 这是因为 queryContext 是 ephemeral (瞬态) 的
  const showTransientComponents = isLastMessage;

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

  if (isToolResult && message) return <ToolMessageBubble message={message} />;

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        <>
          {/* 数据可视化图表 */}
          {hasChartConfig && thread.queryContext?.dataQuery && showTransientComponents && (
            <div className="mb-4">
              <DataChartDisplay dataQuery={thread.queryContext.dataQuery} />
            </div>
          )}

          {/* 数据洞察 */}
          {hasInsight && thread.queryContext?.insight && showTransientComponents && (
            <InsightDisplay insight={thread.queryContext.insight} />
          )}

          {/* 流式文字内容 - AI 的分析 */}
          {contentString.length > 0 && (
            <div className="py-1">
              <MarkdownText shouldAnimate={isLastMessage && isLoading}>
                {contentString}
              </MarkdownText>
            </div>
          )}

          {/* 推荐问题 */}
          {hasSimilarQuestions && thread.queryContext?.similarQuestions && showTransientComponents && (
            <SimilarQuestions 
              questions={thread.queryContext.similarQuestions.questions}
              onSelectQuestion={handleSelectQuestion}
            />
          )}

          {toolCalls.length > 0 && (
            <div className="flex w-full flex-col items-start gap-2">
              {toolCalls.map((toolCall, idx) => (
                <ToolCallTable
                  key={`${toolCall.id || "tool-call"}-${idx}`}
                  toolCall={toolCall}
                />
              ))}
            </div>
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
          {contentString.length > 0 && (
            <div
              className={cn(
                "mr-auto flex items-center gap-2 transition-opacity duration-200",
                isLastMessage ? "opacity-100" : "opacity-0 group-hover:opacity-100"
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
                handleRegenerate={parentCheckpoint ? () => handleRegenerate(parentCheckpoint) : undefined}
                feedbackContext={feedbackContext}
              />
            </div>
          )}
        </>
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
