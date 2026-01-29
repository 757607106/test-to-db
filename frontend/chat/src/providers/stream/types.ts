/**
 * Stream Provider 类型定义
 */

import { type Message } from "@langchain/langgraph-sdk";
import { type UIMessage, type RemoveUIMessage } from "@langchain/langgraph-sdk/react-ui";
import { type UseStream } from "@langchain/langgraph-sdk/react";
import { type QueryContext } from "@/types/stream-events";

/**
 * 状态类型
 */
export type StateType = { messages: Message[]; ui?: UIMessage[] };

/**
 * 流更新类型定义
 */
export type BagType = {
  UpdateType: {
    messages?: Message[] | Message | string;
    ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
    context?: Record<string, unknown>;
  };
  CustomEventType: UIMessage | RemoveUIMessage;
};

/**
 * 基础 Stream 上下文类型
 */
export type StreamContextType = UseStream<StateType, BagType>;

/**
 * 扩展的 Stream 上下文类型，包含查询上下文
 */
export type ExtendedStreamContextType = StreamContextType & {
  queryContext: QueryContext;
  resetQueryContext: () => void;
};
