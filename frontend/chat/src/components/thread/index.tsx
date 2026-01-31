/**
 * Thread 组件
 * 主要的聊天对话界面
 * 
 * 模块结构：
 * - helpers.tsx: 辅助组件 (StickyToBottomContent, ScrollToBottom, OpenGitHubRepo)
 * - messages/: 消息组件 (ai.tsx, human.tsx, etc.)
 * - history/: 历史记录组件
 * - artifact.tsx: Artifact 相关组件
 */

import { v4 as uuidv4 } from "uuid";
import React, { Fragment, FormEvent, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useStreamContext, StateType } from "@/providers/Stream";
import { Button } from "../ui/button";
import { Checkpoint, Message } from "@langchain/langgraph-sdk";
import { AssistantMessage, AssistantMessageLoading, StageMessageBubble } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import {
  DO_NOT_RENDER_ID_PREFIX,
  ensureToolCallsHaveResponses,
} from "@/lib/ensure-tool-responses";
import { LangGraphLogoSVG } from "../icons/langgraph";
import { TooltipIconButton } from "./tooltip-icon-button";
import {
  LoaderCircle,
  PanelRightOpen,
  PanelRightClose,
  SquarePen,
  XIcon,
  Plus,
} from "lucide-react";
import { useQueryState, parseAsBoolean, parseAsInteger } from "nuqs";
import { StickToBottom } from "use-stick-to-bottom";
import ThreadHistory from "./history";
import { toast } from "sonner";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { Label } from "../ui/label";
import { useFileUpload } from "@/hooks/use-file-upload";
import { ContentBlocksPreview } from "./ContentBlocksPreview";
import {
  useArtifactOpen,
  ArtifactContent,
  ArtifactTitle,
  useArtifactContext,
} from "./artifact";
import { DatabaseConnectionSelector } from "@/components/database-connection-selector";
import { AgentSelector } from "@/components/ui/agent-selector";

// 辅助组件（已拆分到 helpers.tsx）
import { StickyToBottomContent, ScrollToBottom } from "./helpers";

export function Thread() {
  const [artifactContext, setArtifactContext] = useArtifactContext();
  const [artifactOpen, closeArtifact] = useArtifactOpen();

  const [threadId, _setThreadId] = useQueryState("threadId");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );
  const [input, setInput] = useState("");
  // 使用URL参数存储连接ID，这样点赞功能可以正确获取
  const [selectedConnectionId, setSelectedConnectionId] = useQueryState(
    "connectionId",
    parseAsInteger.withDefault(0),
  );
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  // 新增: 跟踪数据库和智能体的数量
  const [connectionCount, setConnectionCount] = useState<number>(0);
  const [agentCount, setAgentCount] = useState<number>(0);
  const {
    contentBlocks,
    setContentBlocks,
    handleFileUpload,
    dropRef,
    removeBlock,
    resetBlocks: _resetBlocks,
    dragOver,
    handlePaste,
  } = useFileUpload();
  const [firstTokenReceived, setFirstTokenReceived] = useState(false);
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");

  const stream = useStreamContext();
  // 官方实现：直接使用 stream.messages，不做复杂的去重处理
  const messages = stream.messages;
  const isLoading = stream.isLoading;

  const lastError = useRef<string | undefined>(undefined);

  const setThreadId = (id: string | null) => {
    _setThreadId(id);

    // close artifact and reset artifact context
    closeArtifact();
    setArtifactContext({});
  };

  useEffect(() => {
    if (!stream.error) {
      lastError.current = undefined;
      return;
    }
    try {
      const message = (stream.error as any).message;
      if (!message || lastError.current === message) {
        // Message has already been logged. do not modify ref, return early.
        return;
      }

      // Message is defined, and it has not been logged yet. Save it, and send the error
      lastError.current = message;
      toast.error("An error occurred. Please try again.", {
        description: (
          <p>
            <strong>Error:</strong> <code>{message}</code>
          </p>
        ),
        richColors: true,
        closeButton: true,
      });
    } catch {
      // no-op
    }
  }, [stream.error]);

  // TODO: this should be part of the useStream hook
  const prevMessageLength = useRef(0);
  useEffect(() => {
    if (
      messages.length !== prevMessageLength.current &&
      messages?.length &&
      messages[messages.length - 1].type === "ai"
    ) {
      setFirstTokenReceived(true);
    }

    prevMessageLength.current = messages.length;
  }, [messages]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if ((input.trim().length === 0 && contentBlocks.length === 0) || isLoading)
      return;
    
    // 新增: 检查是否需要选择数据库
    if (!selectedConnectionId && connectionCount > 0) {
      toast.error("请先选择数据库", {
        description: connectionCount > 1 
          ? `系统中有 ${connectionCount} 个数据库连接，请在底部工具栏选择一个数据库后再发送消息。`
          : "请稍等数据库加载完成...",
        richColors: true,
        closeButton: true,
      });
      return;
    }
    
    // 新增: 如果有多个智能体但未选择，提示用户
    if (!selectedAgentId && agentCount > 1) {
      toast.warning("提示: 您未选择智能体", {
        description: `系统中有 ${agentCount} 个可用的智能体，当前使用默认分析模式。您可以在底部工具栏选择特定的智能体。`,
        richColors: true,
        closeButton: true,
        duration: 5000,
      });
      // 这里不返回，只是提示，仍然允许发送（使用默认分析模式）
    }
    
    // 重置查询上下文，避免显示旧数据导致闪烁
    stream.resetQueryContext();
    
    setFirstTokenReceived(false);

    const newHumanMessage: Message = {
      id: uuidv4(),
      type: "human",
      content: [
        ...(input.trim().length > 0 ? [{ type: "text", text: input }] : []),
        ...contentBlocks,
      ] as Message["content"],
      // 将连接ID和智能体ID放到additional_kwargs中
      additional_kwargs: {
        ...(selectedConnectionId ? { connection_id: selectedConnectionId } : {}),
        ...(selectedAgentId ? { agent_id: selectedAgentId } : {}),
      },
    };

    const toolMessages = ensureToolCallsHaveResponses(Array.isArray(stream.messages) ? stream.messages : []);

    const context = {
      ...(Object.keys(artifactContext).length > 0 ? artifactContext : {}),
      ...(selectedConnectionId ? { connectionId: selectedConnectionId } : {}),
    };

    stream.submit(
      {
        messages: [...toolMessages, newHumanMessage],
        // 直接传递 connection_id 和 agent_id 到 state 根级别
        connection_id: selectedConnectionId || undefined,
        agent_id: selectedAgentId || undefined,
        context: Object.keys(context).length > 0 ? context : undefined,
      } as any,
      {
        streamMode: ["values"],  // 只使用 values 模式，避免内部 LLM 调用的 JSON 响应泄漏
        streamSubgraphs: true,
        streamResumable: true,
        optimisticValues: (prev: StateType) => ({
          ...prev,
          context: Object.keys(context).length > 0 ? context : undefined,
          messages: [
            ...(prev.messages ?? []),
            ...toolMessages,
            newHumanMessage,
          ],
        }),
      } as any,
    );

    setInput("");
    setContentBlocks([]);
  };

  const handleRegenerate = (
    parentCheckpoint: Checkpoint | null | undefined,
  ) => {
    // Do this so the loading state is correct
    prevMessageLength.current = prevMessageLength.current - 1;
    setFirstTokenReceived(false);
    stream.submit(undefined, {
      checkpoint: parentCheckpoint,
      streamMode: ["values"],  // 只使用 values 模式
      streamSubgraphs: true,
      streamResumable: true,
    } as any);
  };

  const chatStarted = !!threadId || !!messages.length;
  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const stageMessages = stream.queryContext?.stageMessages ?? [];
  const filteredMessages = messages.filter(
    (m) =>
      !m.id?.startsWith(DO_NOT_RENDER_ID_PREFIX) &&
      m.type !== "tool",
  );
  let lastAssistantIndex = -1;
  for (let i = filteredMessages.length - 1; i >= 0; i -= 1) {
    if (filteredMessages[i].type === "ai") {
      lastAssistantIndex = i;
      break;
    }
  }
  const stageInsertIndex =
    lastAssistantIndex >= 0 ? lastAssistantIndex : filteredMessages.length;
  const shouldAppendStageMessages = stageInsertIndex === filteredMessages.length;
  const stageMessageNodes =
    stageMessages.length > 0
      ? stageMessages.map((stage, index) => (
          <StageMessageBubble
            key={`stage-${stage.step ?? "stage"}-${stage.time_ms}-${index}`}
            message={stage.message}
            step={stage.step}
            timeMs={stage.time_ms}
          />
        ))
      : null;

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <div className="relative hidden lg:flex">
        <motion.div
          className="absolute z-20 h-full overflow-hidden border-r bg-white"
          style={{ width: 300 }}
          animate={
            isLargeScreen
              ? { x: chatHistoryOpen ? 0 : -300 }
              : { x: chatHistoryOpen ? 0 : -300 }
          }
          initial={{ x: -300 }}
          transition={
            isLargeScreen
              ? { type: "spring", stiffness: 300, damping: 30 }
              : { duration: 0 }
          }
        >
          <div
            className="relative h-full"
            style={{ width: 300 }}
          >
            <ThreadHistory />
          </div>
        </motion.div>
      </div>

      <div
        className={cn(
          "grid w-full grid-cols-[1fr_0fr] transition-all duration-500",
          artifactOpen && "grid-cols-[3fr_2fr]",
        )}
      >
        <motion.div
          className={cn(
            "relative flex min-w-0 flex-1 flex-col overflow-hidden",
            !chatStarted && "grid-rows-[1fr]",
          )}
          layout={isLargeScreen}
          animate={{
            marginLeft: chatHistoryOpen ? (isLargeScreen ? 300 : 0) : 0,
            width: chatHistoryOpen
              ? isLargeScreen
                ? "calc(100% - 300px)"
                : "100%"
              : "100%",
          }}
          transition={
            isLargeScreen
              ? { type: "spring", stiffness: 300, damping: 30 }
              : { duration: 0 }
          }
        >
          {!chatStarted && (
            <div className="absolute top-0 left-0 z-10 flex w-full items-center justify-between gap-3 p-2 pl-4">
              <div>
                {(!chatHistoryOpen || !isLargeScreen) && (
                  <Button
                    className="hover:bg-gray-100"
                    variant="ghost"
                    onClick={() => setChatHistoryOpen((p) => !p)}
                  >
                    {chatHistoryOpen ? (
                      <PanelRightOpen className="size-5" />
                    ) : (
                      <PanelRightClose className="size-5" />
                    )}
                  </Button>
                )}
              </div>
              {/*<div className="absolute top-2 right-4 flex items-center">*/}
              {/*  <OpenGitHubRepo />*/}
              {/*</div>*/}
            </div>
          )}
          {chatStarted && (
            <div className="relative z-10 flex items-center justify-between gap-3 p-2">
              <div className="relative flex items-center justify-start gap-2">
                <div className="absolute left-0 z-10">
                  {(!chatHistoryOpen || !isLargeScreen) && (
                    <Button
                      className="hover:bg-gray-100"
                      variant="ghost"
                      onClick={() => setChatHistoryOpen((p) => !p)}
                    >
                      {chatHistoryOpen ? (
                        <PanelRightOpen className="size-5" />
                      ) : (
                        <PanelRightClose className="size-5" />
                      )}
                    </Button>
                  )}
                </div>
                <motion.button
                  className="flex cursor-pointer items-center gap-2"
                  onClick={() => setThreadId(null)}
                  animate={{
                    marginLeft: !chatHistoryOpen ? 48 : 0,
                  }}
                  transition={{
                    type: "spring",
                    stiffness: 300,
                    damping: 30,
                  }}
                >
                  <LangGraphLogoSVG
                    width={32}
                    height={32}
                  />
                  <span className="text-xl font-semibold tracking-tight">
                    任我行智能BI
                  </span>
                </motion.button>
              </div>

              <div className="flex items-center gap-4">
                {/*<div className="flex items-center">*/}
                {/*  <OpenGitHubRepo />*/}
                {/*</div>*/}
                <TooltipIconButton
                  size="lg"
                  className="p-4"
                  tooltip="新对话"
                  variant="ghost"
                  onClick={() => setThreadId(null)}
                >
                  <SquarePen className="size-5" />
                </TooltipIconButton>
              </div>

              <div className="from-background to-background/0 absolute inset-x-0 top-full h-5 bg-gradient-to-b" />
            </div>
          )}

          <StickToBottom className="relative flex-1 overflow-hidden">
            <StickyToBottomContent
              className={cn(
                "absolute inset-0 overflow-y-scroll px-4 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent",
                !chatStarted && "mt-[25vh] flex flex-col items-stretch",
                chatStarted && "grid grid-rows-[1fr_auto]",
              )}
              contentClassName="pt-8 pb-16  max-w-3xl mx-auto flex flex-col gap-4 w-full"
              content={
                <>
                  {filteredMessages.map((message, index) => (
                    <Fragment key={message.id || `${message.type}-${index}`}>
                      {index === stageInsertIndex && stageMessageNodes}
                      {message.type === "human" ? (
                        <HumanMessage
                          message={message}
                          isLoading={isLoading}
                        />
                      ) : (
                        <AssistantMessage
                          message={message}
                          isLoading={isLoading}
                          handleRegenerate={handleRegenerate}
                          connectionId={selectedConnectionId || undefined}
                        />
                      )}
                    </Fragment>
                  ))}
                  {shouldAppendStageMessages && stageMessageNodes}
                  {/* Special rendering case where there are no AI/tool messages, but there is an interrupt.
                    We need to render it outside of the messages list, since there are no messages to render */}
                  {hasNoAIOrToolMessages && !!stream.interrupt && (
                    <AssistantMessage
                      key="interrupt-msg"
                      message={undefined}
                      isLoading={isLoading}
                      handleRegenerate={handleRegenerate}
                      connectionId={selectedConnectionId || undefined}
                    />
                  )}
                  {/* Loading 指示器：只在没有收到第一个 token 时显示 */}
                  {isLoading && !firstTokenReceived && (
                    <AssistantMessageLoading />
                  )}
                </>
              }
              footer={
                <div className="sticky bottom-0 flex flex-col items-center gap-8 bg-background/80 backdrop-blur-xl">
                  {!chatStarted && (
                    <div className="flex items-center gap-3">
                      <LangGraphLogoSVG className="h-8 flex-shrink-0" />
                      <h1 className="text-2xl font-semibold tracking-tight">
                        任我行智能BI
                      </h1>
                    </div>
                  )}

                  <ScrollToBottom className="animate-in fade-in-0 zoom-in-95 absolute bottom-full left-1/2 mb-4 -translate-x-1/2" />

                  <div
                    ref={dropRef}
                    className={cn(
                      "relative z-10 mx-auto mb-8 w-full max-w-3xl rounded-[24px] shadow-lg transition-all bg-white/80 dark:bg-[#1C1C1E]/80 backdrop-blur-md border border-white/20 dark:border-white/10",
                      dragOver
                        ? "border-primary border-2 border-dotted"
                        : "border border-black/5 dark:border-white/5",
                    )}
                  >
                    <form
                      onSubmit={handleSubmit}
                      className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2"
                    >
                      <ContentBlocksPreview
                        blocks={contentBlocks}
                        onRemove={removeBlock}
                      />
                      <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onPaste={handlePaste}
                        onKeyDown={(e) => {
                          if (
                            e.key === "Enter" &&
                            !e.shiftKey &&
                            !e.metaKey &&
                            !e.nativeEvent.isComposing
                          ) {
                            e.preventDefault();
                            const el = e.target as HTMLElement | undefined;
                            const form = el?.closest("form");
                            form?.requestSubmit();
                          }
                        }}
                        placeholder="请输入您的消息..."
                        className="field-sizing-content resize-none border-none bg-transparent p-3.5 pb-0 shadow-none ring-0 outline-none focus:ring-0 focus:outline-none"
                      />

                      <div className="flex items-center justify-between p-2 pt-4">
                        <div className="flex items-center gap-4">
                          <Label
                            htmlFor="file-input"
                            className="flex cursor-pointer items-center gap-2 hover:text-gray-800 transition-colors"
                          >
                            <Plus className="size-4 text-gray-600" />
                            <span className="text-sm text-gray-600">
                              上传PDF或图片
                            </span>
                          </Label>
                          <input
                            id="file-input"
                            type="file"
                            onChange={handleFileUpload}
                            multiple
                            accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
                            className="hidden"
                          />

                          <div className="border-l border-gray-200 pl-4">
                            <DatabaseConnectionSelector
                              value={selectedConnectionId}
                              onChange={setSelectedConnectionId}
                              onLoaded={setConnectionCount}
                            />
                          </div>
                          <div className="border-l border-gray-200 pl-4">
                            <AgentSelector
                              value={selectedAgentId}
                              onChange={setSelectedAgentId}
                              onLoaded={setAgentCount}
                            />
                          </div>
                        </div>

                        {stream.isLoading ? (
                          <Button
                            key="stop"
                            onClick={() => stream.stop()}
                            className="shadow-md"
                          >
                            <LoaderCircle className="h-4 w-4 animate-spin" />
                            取消
                          </Button>
                        ) : (
                          <Button
                            type="submit"
                            className="shadow-md transition-all"
                            disabled={
                              isLoading ||
                              (!input.trim() && contentBlocks.length === 0)
                            }
                          >
                            发送
                          </Button>
                        )}
                      </div>
                    </form>
                  </div>
                </div>
              }
            />
          </StickToBottom>
        </motion.div>
        <div className="relative flex flex-col border-l">
          <div className="absolute inset-0 flex min-w-[30vw] flex-col">
            <div className="grid grid-cols-[1fr_auto] border-b p-4">
              <ArtifactTitle className="truncate overflow-hidden" />
              <button
                onClick={closeArtifact}
                className="cursor-pointer"
              >
                <XIcon className="size-5" />
              </button>
            </div>
            <ArtifactContent className="relative flex-grow" />
          </div>
        </div>
      </div>
    </div>
  );
}
