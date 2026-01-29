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
import { Fragment, useCallback, useMemo, useState } from "react";
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
import { DataChartDisplay } from "./DataChartDisplay";
import { InsightDisplay } from "./InsightDisplay";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  Sparkles,
} from "lucide-react";
import { SQL_STEP_LABELS, type SQLStepEvent } from "@/types/stream-events";

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

function formatDuration(ms: number | undefined) {
  if (ms == null) return "";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

export function ThinkingPanel({
  steps,
  isLoading,
}: {
  steps: SQLStepEvent[];
  isLoading: boolean;
}) {
  const [open, setOpen] = useState(false);

  const normalizedSteps = useMemo(() => {
    const order = [
      "cache_hit",
      "intent_analysis",
      "query_planning",
      "query_rewrite",
      "skill_routing",
      "schema_agent",
      "schema_mapping",
      "clarification",
      "few_shot",
      "llm_parse",
      "sql_fix",
      "sql_generator",
      "final_sql",
      "sql_executor",
      "data_analysis",
      "data_analyst",
      "chart_generation",
      "chart_generator",
      "result_aggregator",
      "error_recovery",
      "general_chat",
    ];

    const rank = new Map<string, number>(order.map((k, i) => [k, i]));
    const dedup = new Map<string, SQLStepEvent>();

    for (const s of steps) {
      if (!s?.step) continue;
      const prev = dedup.get(s.step);
      if (!prev) {
        dedup.set(s.step, s);
        continue;
      }
      const score = (st: SQLStepEvent["status"]) => {
        if (st === "error") return 3;
        if (st === "running") return 2;
        if (st === "completed") return 1;
        return 0;
      };
      if (score(s.status) >= score(prev.status)) dedup.set(s.step, s);
    }

    return Array.from(dedup.values()).sort((a, b) => {
      const ra = rank.get(a.step) ?? 10_000;
      const rb = rank.get(b.step) ?? 10_000;
      if (ra !== rb) return ra - rb;
      return a.step.localeCompare(b.step);
    });
  }, [steps]);

  const hasAny = normalizedSteps.length > 0;
  const hasRunning = normalizedSteps.some((s) => s.status === "running");
  const hasError = normalizedSteps.some((s) => s.status === "error");

  if (!hasAny && !isLoading) return null;

  const title = hasRunning || isLoading ? "思考中…" : hasError ? "执行遇到问题" : "思考过程";
  const badge = hasRunning || isLoading ? "进行中" : hasError ? "异常" : "完成";

  return (
    <div className="rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 overflow-hidden shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-50/60 dark:bg-slate-900/40 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={cn(
              "h-8 w-8 rounded-lg flex items-center justify-center",
              hasError
                ? "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400"
                : "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400",
            )}
          >
            {hasError ? (
              <AlertCircle className="h-4 w-4" />
            ) : hasRunning || isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
          </div>
          <div className="flex flex-col items-start min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-semibold text-sm text-slate-800 dark:text-slate-200 truncate">
                {title}
              </span>
              <span
                className={cn(
                  "text-xs font-medium px-2 py-0.5 rounded-full shrink-0",
                  hasError
                    ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                    : hasRunning || isLoading
                      ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                      : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
                )}
              >
                {badge}
              </span>
            </div>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {hasAny ? `${normalizedSteps.length} 个步骤` : "等待步骤信息…"}
            </span>
          </div>
        </div>
        <div className="text-slate-400">
          {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </div>
      </button>

      {open && (
        <div className="px-4 py-3 bg-white dark:bg-slate-950">
          <div className="flex flex-col gap-2">
            {normalizedSteps.map((s) => {
              const label = SQL_STEP_LABELS[s.step] ?? s.step;
              const statusLabel =
                s.status === "running"
                  ? "进行中"
                  : s.status === "completed"
                    ? "完成"
                    : s.status === "error"
                      ? "异常"
                      : s.status === "skipped"
                        ? "跳过"
                        : s.status;

              return (
                <div
                  key={`${s.step}`}
                  className="rounded-lg border border-slate-200 dark:border-slate-800 overflow-hidden"
                >
                  <div className="flex items-center justify-between gap-3 px-3 py-2 bg-slate-50/50 dark:bg-slate-900/30">
                    <div className="flex items-center gap-2 min-w-0">
                      {s.status === "running" ? (
                        <Loader2 className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 animate-spin shrink-0" />
                      ) : s.status === "error" ? (
                        <AlertCircle className="h-3.5 w-3.5 text-red-600 dark:text-red-400 shrink-0" />
                      ) : s.status === "completed" ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                      ) : (
                        <div className="h-3.5 w-3.5 shrink-0" />
                      )}
                      <span className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
                        {label}
                      </span>
                      <span
                        className={cn(
                          "text-[11px] px-2 py-0.5 rounded-full shrink-0",
                          s.status === "error"
                            ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                            : s.status === "running"
                              ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                              : s.status === "completed"
                                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
                        )}
                      >
                        {statusLabel}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500 dark:text-slate-400 shrink-0">
                      {s.time_ms ? formatDuration(s.time_ms) : ""}
                    </span>
                  </div>
                  {s.result && (
                    <div className="px-3 py-2 bg-white dark:bg-slate-950 border-t border-slate-200 dark:border-slate-800">
                      <pre className="text-xs text-slate-700 dark:text-slate-300 whitespace-pre-wrap break-words max-h-48 overflow-auto">
                        {s.result}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
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
  const lastRenderableMessageId = useMemo(() => {
    const last = [...thread.messages]
      .reverse()
      .find(
        (m) =>
          m.type !== "tool" && !m.id?.startsWith(DO_NOT_RENDER_ID_PREFIX),
      );
    return last?.id;
  }, [thread.messages]);
  const isLastMessage = lastRenderableMessageId === message?.id;
  const hasNoAIOrToolMessages = !thread.messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const meta = message ? thread.getMessagesMetadata(message) : undefined;
  const threadInterrupt = thread.interrupt;

  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;
  const isToolResult = message?.type === "tool";

  // 数据可视化相关
  // 检查当前消息是否关联了 queryContext 数据
  // 逻辑优化：
  // 1. 如果是最后一条消息，直接使用当前的 queryContext
  // 2. 如果是历史消息，我们需要一种机制来关联数据。目前最简单的方式是假设只有最后一条消息持有当前的 queryContext。
  //    为了支持历史记录回看，我们需要确认 queryContext 是否包含了历史数据或者消息本身是否携带了这些数据。
  //    在此项目中，StreamProvider 似乎只维护了"当前"的 queryContext。
  //    为了让历史消息也能显示图表，我们暂时放宽限制：如果 thread.queryContext 存在且对应的消息 ID 匹配（如果有这个字段）
  //    或者，我们简单地只在最后一条消息显示，但用户反馈"看不到了"，说明可能在流式传输结束后，isLastMessage 状态变化或者 queryContext 被清空了？
  //    通常 queryContext 会保留直到下一次查询。
  //    用户的问题可能是：当生成结束后，虽然还是最后一条消息，但某些状态可能变了。
  //    或者用户进行了新的对话，旧的消息就不显示图表了。
  //    为了解决这个问题，我们需要查看 artifact 或其他持久化存储。
  //    但在现有架构下，最稳妥的修复是：确保只要是最后一条消息，或者该消息触发了查询（需要后端配合将 ID 写入），就显示。
  //    
  //    根据现有代码，thread.queryContext 是全局单例的。这意味着只有最后一次查询的结果被保存在 Context 中。
  //    因此，历史消息确实无法显示旧的图表/推荐问题，除非这些数据被持久化到了 message.content 或 artifact 中。
  //    
  //    现在的临时修复（针对用户反馈"看不到了"）：
  //    用户可能是在流式生成过程中能看到，生成完（或者状态切换）后消失了。
  //    或者用户指的历史记录里没有。
  //    
  //    如果在历史记录中也需要，我们需要检查 message 中是否包含 tool_call 结果，并从中提取数据。
  //    但这里的 DataChartDisplay 依赖于 `dataQuery` 对象。
  //    
  //    让我们先确保在"当前会话"中，只要数据存在就显示，稍微放宽 isLastMessage 的判断，
  //    或者确认一下是否因为 key 变化导致重渲染丢失。
  
  // 修正：移除 isLastMessage 限制，只要 queryContext 存在且属于当前上下文周期即可。
  // 但这样会导致所有 AI 消息都显示同一个图表。
  // 正确的做法是：图表应该只关联到触发它的那条消息。
  // 假设当前场景用户是在进行单轮或多轮对话，期望最新的结果常驻。
  
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

  if (isToolResult) return null;

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        <>
          {showTransientComponents && (
            <div className="mb-4">
              <ThinkingPanel
                steps={thread.queryContext?.sqlSteps ?? []}
                isLoading={isLoading}
              />
            </div>
          )}

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
              <MarkdownText>{contentString}</MarkdownText>
            </div>
          )}

          {/* 推荐问题 */}
          {hasSimilarQuestions && thread.queryContext?.similarQuestions && showTransientComponents && (
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
