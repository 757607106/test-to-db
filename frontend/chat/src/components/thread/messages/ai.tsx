
import { parsePartialJson } from "@langchain/core/output_parsers";
import { useStreamContext } from "@/providers/Stream";
import { AIMessage, Checkpoint, Message } from "@langchain/langgraph-sdk";
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
  return (
    <>
      {/* 处理澄清类型的 interrupt */}
      {isClarificationInterrupt(interruptValue) &&
        (isLastMessage || hasNoAIOrToolMessages) && (
          <ClarificationInterruptView interrupt={interruptValue} />
        )}
      {/* 处理 Agent Inbox 类型的 interrupt */}
      {isAgentInboxInterruptSchema(interruptValue) &&
        !isClarificationInterrupt(interruptValue) &&
        (isLastMessage || hasNoAIOrToolMessages) && (
          <ThreadView interrupt={interruptValue} />
        )}
      {/* 处理其他通用类型的 interrupt */}
      {interruptValue &&
      !isAgentInboxInterruptSchema(interruptValue) &&
      !isClarificationInterrupt(interruptValue) &&
      (isLastMessage || hasNoAIOrToolMessages) ? (
        <GenericInterruptView interrupt={interruptValue} />
      ) : null}
    </>
  );
}

// Helper function to check if content is pure JSON or partial JSON (should not be displayed as text)
// This handles both complete JSON and streaming partial JSON responses
function isPureJsonContent(text: string): boolean {
  if (!text || text.length === 0) return false;
  const trimmed = text.trim();
  
  // Check if it starts with JSON array or object syntax
  if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
    // For complete JSON, try to parse it
    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || 
        (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
      try {
        JSON.parse(trimmed);
        return true;
      } catch {
        // Continue to pattern matching for partial JSON
      }
    }
    
    // For streaming/partial JSON, check if it looks like JSON structure
    // Match patterns like: [{"key, {"key": , [{ "table_id", etc.
    const jsonPatterns = [
      /^\[\s*\{/,                    // Starts with [{ (JSON array of objects)
      /^\{\s*"/,                     // Starts with {" (JSON object with string key)
      /^\[\s*"/,                     // Starts with [" (JSON array of strings)
      /^\{\s*'[a-zA-Z_]/,           // Starts with {'key (non-standard but possible)
      /^\[\s*\d/,                    // Starts with [1 (JSON array of numbers)
      /^\{\s*"[a-zA-Z_][a-zA-Z0-9_]*"\s*:/,  // Object with key pattern {"key":
    ];
    
    if (jsonPatterns.some(pattern => pattern.test(trimmed))) {
      return true;
    }
  }
  
  return false;
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
  const rawContentString = getContentString(content);
  // Filter out pure JSON content that should not be displayed as text (internal tool results)
  const contentString = isPureJsonContent(rawContentString) ? '' : rawContentString;
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
  const hasAnthropicToolCalls = !!anthropicStreamedToolCalls?.length;
  const isToolResult = message?.type === "tool";

  // Hide tool result messages - they are now displayed within ToolCalls component
  if (isToolResult) {
    return null;
  }

  // Get tool results for matching with tool calls
  const toolResultMessages = messages.filter(
    (m): m is import("@langchain/langgraph-sdk").ToolMessage => m.type === "tool"
  );

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        {contentString.length > 0 && (
          <div className="py-1">
            <MarkdownText>{contentString}</MarkdownText>
          </div>
        )}

        {!hideToolCalls && (
          <>
            {hasToolCalls && (
              <ToolCalls
                toolCalls={message.tool_calls}
                toolResults={toolResultMessages.filter(tr =>
                  message.tool_calls?.some(tc => tc.id === tr.tool_call_id)
                )}
              />
            )}
            {!hasToolCalls && hasAnthropicToolCalls && (
              <ToolCalls
                toolCalls={anthropicStreamedToolCalls}
                toolResults={toolResultMessages.filter(tr =>
                  anthropicStreamedToolCalls?.some(tc => tc.id === tr.tool_call_id)
                )}
              />
            )}
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
