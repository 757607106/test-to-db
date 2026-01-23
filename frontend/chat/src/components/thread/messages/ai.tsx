/**
 * AI 消息组件
 * 
 * 基于 LangGraph 官方 streaming 标准实现
 * 
 * 设计原则：
 * 1. messages 模式：仅用于 AI 最终回答的文本内容
 * 2. custom 模式：用于所有工具进度和查询结果（由 QueryPipeline 独立渲染）
 * 3. 所有 ToolMessage 统一隐藏（进度通过 custom 事件展示）
 * 
 * @see https://docs.langchain.com/oss/python/langgraph/streaming
 */
import { useStreamContext } from "@/providers/Stream";
import { Checkpoint, Message, ToolMessage } from "@langchain/langgraph-sdk";
import { getContentString } from "../utils";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { cn } from "@/lib/utils";
import { Fragment } from "react/jsx-runtime";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { ThreadView } from "../agent-inbox";
import { useQueryState, parseAsInteger } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { 
  ClarificationInterruptView, 
  extractClarificationData 
} from "./clarification-interrupt";
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
 * 简化后的渲染逻辑：
 * - 工具消息：统一返回 null（进度通过 QueryPipeline 展示）
 * - AI 消息：只渲染文本内容
 * 
 * QueryPipeline 和数据展示组件已移至 index.tsx 独立渲染
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
  // 从 URL 参数获取 connectionId
  const [connectionId] = useQueryState(
    "connectionId",
    parseAsInteger.withDefault(0),
  );
  
  // 从 URL 参数获取 threadId
  const [threadId] = useQueryState("threadId");

  const thread = useStreamContext();
  const { queryContext } = thread;
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
  
  // 工具消息检测
  const isToolResult = message?.type === "tool";

  // ========================================
  // 简化逻辑：所有工具消息统一隐藏
  // 工具进度通过 custom 事件在 QueryPipeline 中展示
  // ========================================
  if (isToolResult) {
    return null;
  }

  // 渲染 AI 消息 - 只渲染文本内容
  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-3">
        {/* 文本内容（AI 的最终回答） */}
        {contentString.length > 0 && (
          <div className="py-1">
            <MarkdownText>{contentString}</MarkdownText>
          </div>
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

        {/* 操作栏 - 仅在有内容时显示 */}
        {contentString.length > 0 && (
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
              feedbackContext={
                queryContext?.dataQuery && connectionId
                  ? {
                      question: contentString,
                      sql: (queryContext.sqlSteps as any[])?.find((s: any) => s.step === "llm_parse" || s.step === "final_sql")?.result || "",
                      connectionId: connectionId,
                      threadId: threadId || undefined,
                    }
                  : undefined
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * 加载中状态组件
 * 
 * 简化后只显示基础加载动画
 * QueryPipeline 的实时进度在 index.tsx 中独立渲染
 */
export function AssistantMessageLoading() {
  return (
    <div className="mr-auto flex items-start gap-2">
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 flex h-auto items-center gap-3 rounded-xl px-4 py-2.5 shadow-sm">
        <div className="flex items-center gap-1">
          <div className="bg-blue-500 h-2 w-2 animate-[pulse_1.5s_ease-in-out_infinite] rounded-full shadow-sm shadow-blue-300"></div>
          <div className="bg-blue-500 h-2 w-2 animate-[pulse_1.5s_ease-in-out_0.3s_infinite] rounded-full shadow-sm shadow-blue-300"></div>
          <div className="bg-blue-500 h-2 w-2 animate-[pulse_1.5s_ease-in-out_0.6s_infinite] rounded-full shadow-sm shadow-blue-300"></div>
        </div>
        <span className="text-sm font-medium text-blue-700">思考中...</span>
      </div>
    </div>
  );
}

