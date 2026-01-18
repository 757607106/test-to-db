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
import { useQueryState, parseAsBoolean } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { ClarificationInterruptView, isClarificationInterrupt } from "./clarification-interrupt";
import { useArtifact } from "../artifact";

/**
 * Fix duplicated tool_call_id issue from LangGraph backend
 * Some tool_call_ids are incorrectly duplicated (e.g., "call_xxxcall_xxx" instead of "call_xxx")
 * This function detects and fixes such duplications
 */
function fixDuplicatedToolCallId(toolCallId: string): string {
  if (!toolCallId) return toolCallId;
  
  // Check if the ID is duplicated (e.g., "call_xxxcall_xxx")
  // Pattern: if the string is exactly twice the length of its first half and both halves are identical
  const len = toolCallId.length;
  if (len % 2 === 0) {
    const half = len / 2;
    const firstHalf = toolCallId.substring(0, half);
    const secondHalf = toolCallId.substring(half);
    if (firstHalf === secondHalf) {
      return firstHalf;
    }
  }
  
  return toolCallId;
}

/**
 * Check if a tool call ID matches a tool result's tool_call_id
 * Handles the case where tool_call_id might be duplicated
 */
function toolCallIdMatches(toolCallId: string, toolResultId: string): boolean {
  if (!toolCallId || !toolResultId) return false;
  
  // Direct match
  if (toolCallId === toolResultId) return true;
  
  // Try fixing duplicated ID
  const fixedResultId = fixDuplicatedToolCallId(toolResultId);
  if (toolCallId === fixedResultId) return true;
  
  // Also check if the tool call ID itself might be duplicated (less common)
  const fixedCallId = fixDuplicatedToolCallId(toolCallId);
  if (fixedCallId === toolResultId || fixedCallId === fixedResultId) return true;
  
  return false;
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
    })
    .filter((tc) => tc.name && tc.name.trim() !== ""); // Filter out empty names
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
