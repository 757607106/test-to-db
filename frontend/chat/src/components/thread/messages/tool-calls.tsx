"use client";

import React, { useState, useMemo, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle,
  Loader,
} from "lucide-react";
import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";

interface ToolCallBoxProps {
  toolCall: NonNullable<AIMessage["tool_calls"]>[0];
  toolResult?: ToolMessage;
}

const ToolCallBox = React.memo<ToolCallBoxProps>(({ toolCall, toolResult }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const { name, args, result, status, resultText } = useMemo(() => {
    const toolName = toolCall?.name?.trim() || "Unknown Tool";
    const toolArgs = toolCall?.args || {};

    let toolResult_content = null;
    let resultAsText = "";

    if (toolResult) {
      try {
        if (typeof toolResult.content === "string") {
          toolResult_content = JSON.parse(toolResult.content);
          resultAsText = toolResult.content;
        } else {
          toolResult_content = toolResult.content;
          resultAsText = JSON.stringify(toolResult.content, null, 2);
        }
      } catch {
        toolResult_content = toolResult.content;
        resultAsText = String(toolResult.content);
      }
    }

    // Determine tool status:
    // 1. Handoff tools (transfer_to_xxx) are always completed immediately
    // 2. Tools with results are completed
    // 3. Otherwise pending
    const isHandoffTool = toolName.startsWith("transfer_to_");
    
    let toolStatus: "pending" | "completed";
    if (toolResult) {
      toolStatus = "completed";
    } else if (isHandoffTool) {
      toolStatus = "completed";
    } else {
      toolStatus = "pending";
    }

    return {
      name: toolName,
      args: toolArgs,
      result: toolResult_content,
      status: toolStatus,
      resultText: resultAsText,
    };
  }, [toolCall, toolResult]);

  const statusIcon = useMemo(() => {
    if (status === "completed") {
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    }
    return <Loader className="w-4 h-4 text-blue-500 animate-spin" />;
  }, [status]);

  const toggleExpanded = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  const hasContent = result || Object.keys(args).length > 0;

  return (
    <div className="w-full mb-2">
      <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
        <button
          onClick={toggleExpanded}
          className="w-full p-3 flex items-center gap-2 text-left transition-colors hover:bg-gray-50 cursor-pointer disabled:cursor-default"
          disabled={!hasContent}
        >
          {hasContent && isExpanded ? (
            <ChevronDown size={14} className="flex-shrink-0 text-gray-600" />
          ) : (
            <ChevronRight size={14} className="flex-shrink-0 text-gray-600" />
          )}
          {statusIcon}
          <span className="text-sm font-medium text-gray-900">{name}</span>
        </button>

        {isExpanded && hasContent && (
          <div className="px-4 pb-4 bg-gray-50">
            {Object.keys(args).length > 0 && (
              <div className="mt-4">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  ARGUMENTS
                </h4>
                <pre className="p-3 bg-white border border-gray-200 rounded text-xs font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap break-all m-0">
                  {JSON.stringify(args, null, 2)}
                </pre>
              </div>
            )}
            {result && (
              <div className="mt-4">
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  RESULT
                </h4>
                <pre className="p-3 bg-white border border-gray-200 rounded text-xs font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap break-all m-0 max-h-96 overflow-y-auto">
                  {typeof result === "string"
                    ? result
                    : JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

ToolCallBox.displayName = "ToolCallBox";

export function ToolCalls({
  toolCalls,
  toolResults,
}: {
  toolCalls: AIMessage["tool_calls"];
  toolResults?: ToolMessage[];
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  // Filter out invalid tool calls
  const validToolCalls = toolCalls.filter(tc => tc && tc.name && tc.name.trim() !== "");

  return (
    <div className="w-full">
      {validToolCalls.map((tc, idx) => {
        // Find corresponding tool result by tool_call_id
        const correspondingResult = toolResults?.find(
          (result) => result.tool_call_id === tc.id
        );

        return (
          <ToolCallBox
            key={tc.id || idx}
            toolCall={tc}
            toolResult={correspondingResult}
          />
        );
      })}
    </div>
  );
}

// Keep ToolResult for backward compatibility (renders nothing, results are shown in ToolCallBox)
export function ToolResult({ message }: { message: ToolMessage }) {
  return null;
}
