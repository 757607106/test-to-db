/**
 * AI 消息组件
 * 
 * 基于 LangGraph SDK 官方标准实现
 * 统一渲染 AI 消息和工具消息，简化过滤逻辑
 * 
 * @see https://github.com/langchain-ai/agent-chat-ui
 */
import { useMemo } from "react";
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
// 智能查询界面组件 - 使用新的统一流水线组件
import { QueryPipeline } from "./QueryPipeline";
import { DataChartDisplay } from "./DataChartDisplay";
import { DataAnalysisDisplay } from "./DataAnalysisDisplay";
import { RecommendedQuestionsDisplay } from "./RecommendedQuestionsDisplay";

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
  
  // 智能查询相关的工具名列表
  const SMART_QUERY_TOOLS = [
    "retrieve_database_schema",
    "generate_sql_query", 
    "execute_sql_query",
    "analyze_user_query"
  ];
  
  // 检查当前消息是否包含智能查询相关的工具调用（用于刷新后也能隐藏工具调用）
  // 对 AI 消息：检查 tool_calls
  // 对工具结果消息：检查 name 字段
  const isSmartQueryToolCall = useMemo(() => {
    if (!message) return false;
    
    // AI 消息：检查 tool_calls
    if (message.type === "ai" && "tool_calls" in message) {
      const toolCalls = (message as AIMessage).tool_calls || [];
      return toolCalls.some(tc => SMART_QUERY_TOOLS.includes(tc.name || ""));
    }
    
    // 工具结果消息：检查 name 字段
    if (message.type === "tool" && "name" in message) {
      return SMART_QUERY_TOOLS.includes((message as ToolMessage).name || "");
    }
    
    return false;
  }, [message]);
  
  // 检查整个对话中是否有智能查询工具调用（用于决定是否显示 QueryPipeline）
  const hasSmartQueryInThread = useMemo(() => {
    const result = messages.some(m => {
      if (m.type === "ai" && "tool_calls" in m) {
        const toolCalls = (m as AIMessage).tool_calls || [];
        return toolCalls.some(tc => SMART_QUERY_TOOLS.includes(tc.name || ""));
      }
      return false;
    });
    return result;
  }, [messages, message?.id]);
  
  // 从历史消息中重建查询上下文（刷新后使用）
  const rebuiltQueryContext = useMemo(() => {
    // 如果已有实时流数据，不需要重建
    if (queryContext?.intentAnalysis || queryContext?.sqlSteps?.length || queryContext?.dataQuery) {
      return null;
    }
    
    // 如果对话中没有智能查询，不需要重建
    if (!hasSmartQueryInThread) {
      return null;
    }
    
    // 从工具结果消息中提取数据
    const toolResults: Record<string, string> = {};
    messages.forEach(m => {
      if (m.type === "tool" && "name" in m && "content" in m) {
        const toolMsg = m as ToolMessage;
        if (SMART_QUERY_TOOLS.includes(toolMsg.name || "")) {
          const contentStr = typeof toolMsg.content === "string" 
            ? toolMsg.content 
            : JSON.stringify(toolMsg.content);
          toolResults[toolMsg.name || ""] = contentStr;
        }
      }
    });
    
    // 尝试解析 execute_sql_query 的结果来重建 dataQuery
    let dataQuery = null;
    if (toolResults["execute_sql_query"]) {
      try {
        const result = JSON.parse(toolResults["execute_sql_query"]);
        if (result.columns && result.rows) {
          dataQuery = {
            columns: result.columns,
            rows: result.rows,
            row_count: result.row_count || result.rows?.length || 0,
            chart_config: result.chart_config,
          };
        }
      } catch {
        // 解析失败，忽略
      }
    }
    
    // 构建简化的历史 sqlSteps
    const sqlSteps = [];
    if (toolResults["retrieve_database_schema"]) {
      sqlSteps.push({
        step: "schema_mapping",
        status: "completed" as const,
        result: toolResults["retrieve_database_schema"],
        time_ms: 0,
      });
    }
    if (toolResults["generate_sql_query"]) {
      sqlSteps.push({
        step: "llm_parse",
        status: "completed" as const,
        result: toolResults["generate_sql_query"],
        time_ms: 0,
      });
    }
    if (toolResults["execute_sql_query"]) {
      sqlSteps.push({
        step: "final_sql",
        status: "completed" as const,
        result: "历史查询结果",
        time_ms: 0,
      });
    }
    
    // 如果没有提取到任何数据，返回 null
    if (sqlSteps.length === 0 && !dataQuery) {
      return null;
    }
    
    return {
      intentAnalysis: toolResults["analyze_user_query"] ? {
        intent_type: "data_query",
        original_query: "",
        parsed_intent: toolResults["analyze_user_query"],
      } : { intent_type: "data_query", original_query: "", parsed_intent: "历史查询" },
      sqlSteps,
      dataQuery,
    };
  }, [queryContext, hasSmartQueryInThread, messages]);
  
  // 最终使用的查询上下文：优先实时数据，其次历史重建
  const effectiveQueryContext = queryContext?.intentAnalysis || queryContext?.sqlSteps?.length || queryContext?.dataQuery
    ? queryContext
    : rebuiltQueryContext;
  
  // 检查是否有智能查询流程数据（用于隐藏原始工具调用显示）
  // 优先使用 queryContext（实时流），其次检查工具调用类型（刷新后）
  const hasQueryProcess = useMemo(() => {
    const hasStreamData = Boolean(
      queryContext?.intentAnalysis || 
      queryContext?.sqlSteps?.length || 
      queryContext?.dataQuery
    );
    return hasStreamData || isSmartQueryToolCall;
  }, [queryContext?.intentAnalysis, queryContext?.sqlSteps?.length, queryContext?.dataQuery, isSmartQueryToolCall]);
  
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
        {/* 统一的智能查询流水线 - 只在最后一条消息显示 */}
        {/* 条件：isLastMessage && (有流数据 || 整个对话中有智能查询工具调用) */}
        {isLastMessage && (hasQueryProcess || hasSmartQueryInThread) && (
          <QueryPipeline 
            queryContext={effectiveQueryContext}
            onSelectQuestion={(question) => {
              // 发送推荐的问题
              thread.submit({
                messages: [{
                  role: "human",
                  content: question,
                }]
              });
            }}
          />
        )}

        {/* 数据可视化图表 - 优先展示在文本之前 */}
        {isLastMessage && effectiveQueryContext?.dataQuery?.chart_config && (
          <DataChartDisplay dataQuery={effectiveQueryContext.dataQuery} />
        )}

        {/* 文本内容（包含回答、数据洞察、建议） - 在图表之后 */}
        {contentString.length > 0 && (
          <div className="py-1">
            <MarkdownText>{contentString}</MarkdownText>
          </div>
        )}

        {/* 数据分析组件 - 用于显示单独的分析步骤（如果有） */}
        {isLastMessage && queryContext?.sqlSteps && (
          <DataAnalysisDisplay 
            analysisStep={queryContext.sqlSteps.find(s => s.step === "data_analysis")}
          />
        )}

        {/* 推荐问题 - 在回答后展示 */}
        {isLastMessage && queryContext?.similarQuestions?.questions && queryContext.similarQuestions.questions.length > 0 && (
          <RecommendedQuestionsDisplay 
            questions={queryContext.similarQuestions.questions}
            onSelect={(question) => {
              // 发送推荐的问题
              thread.submit({
                messages: [{
                  role: "human",
                  content: question,
                }]
              });
            }}
          />
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
            feedbackContext={
              hasQueryProcess && queryContext?.dataQuery
                ? {
                    question: contentString,
                    sql: queryContext.dataQuery.columns ? "SQL executed" : "",
                    connectionId: thread.values?.connection_id,
                    threadId: thread.threadId,
                  }
                : undefined
            }
          />
        </div>
      </div>
    </div>
  );
}

export function AssistantMessageLoading() {
  // 简化加载提示：只显示简单的思考动画，不显示具体步骤
  // 这样可以减少因状态变化导致的闪烁
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
