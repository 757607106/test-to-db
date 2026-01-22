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
import { 
  ClarificationInterruptView, 
  isClarificationInterrupt, 
  extractClarificationData 
} from "./clarification-interrupt";
import { useArtifact } from "../artifact";
// 智能查询界面组件
import { QueryProcessCard } from "./QueryProcessCard";

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
  const { queryContext } = thread;
  const messages = Array.isArray(thread.messages) ? thread.messages : [];
  
  // 检查是否有智能查询流程数据（用于隐藏原始工具调用显示）
  const hasQueryProcess = Boolean(
    queryContext?.intentAnalysis || 
    queryContext?.sqlSteps?.length || 
    queryContext?.dataQuery
  );
  
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

  // 如果隐藏工具调用且是工具结果，或者有智能查询流程且是工具结果，不渲染
  if (isToolResult && (hideToolCalls || hasQueryProcess)) {
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
      <div className="flex w-full flex-col gap-3">
        {/* 统一的智能查询卡片 - 只在最后一条消息显示 */}
        {isLastMessage && hasQueryProcess && (
          <QueryProcessCard 
            queryContext={queryContext}
            onSelectQuestion={(question) => {
              console.log("Selected question:", question);
            }}
          />
        )}

        {/* 文本内容 */}
        {contentString.length > 0 && (
          <div className="py-1">
            <MarkdownText>{contentString}</MarkdownText>
          </div>
        )}

        {/* 工具调用显示 - 当有智能查询流程时隐藏 */}
        {!hideToolCalls && !hasQueryProcess && (hasToolCalls || hasAnthropicToolCalls) && (
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

// 执行阶段映射
const STAGE_LABELS: Record<string, string> = {
  clarification: "理解问题中...",
  cache_check: "检查缓存...",
  cache_hit: "命中缓存",
  schema_analysis: "分析数据库结构...",
  sample_retrieval: "检索相似查询...",
  sql_generation: "生成 SQL 查询...",
  sql_validation: "验证 SQL...",
  sql_execution: "执行查询...",
  analysis: "分析结果...",
  chart_generation: "生成图表...",
  error_recovery: "处理错误...",
  completed: "完成",
};

export function AssistantMessageLoading() {
  const { values } = useStreamContext();
  const currentStage = (values as any)?.current_stage as string | undefined;
  const stageLabel = currentStage ? STAGE_LABELS[currentStage] || "处理中..." : "思考中...";

  return (
    <div className="mr-auto flex items-start gap-2">
      <div className="bg-muted flex h-auto items-center gap-2 rounded-2xl px-4 py-2">
        <div className="flex items-center gap-1">
          <div className="bg-blue-500 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_infinite] rounded-full"></div>
          <div className="bg-blue-500 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_0.5s_infinite] rounded-full"></div>
          <div className="bg-blue-500 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_1s_infinite] rounded-full"></div>
        </div>
        <span className="text-sm text-muted-foreground">{stageLabel}</span>
      </div>
    </div>
  );
}
