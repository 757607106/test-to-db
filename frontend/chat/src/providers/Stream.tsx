import React, {
  createContext,
  useContext,
  ReactNode,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import { useStream, type UseStream } from "@langchain/langgraph-sdk/react";
import { type Message } from "@langchain/langgraph-sdk";
import {
  uiMessageReducer,
  isUIMessage,
  isRemoveUIMessage,
  type UIMessage,
  type RemoveUIMessage,
} from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LangGraphLogoSVG } from "@/components/icons/langgraph";
import { Label } from "@/components/ui/label";
import { ArrowRight } from "lucide-react";
import { PasswordInput } from "@/components/ui/password-input";
import { getApiKey } from "@/lib/api-key";
import { useThreads } from "./Thread";
import { toast } from "sonner";
import {
  type QueryContext,
  type StreamEvent,
  type CacheHitEvent,
  createEmptyQueryContext,
  isStreamEvent,
} from "@/types/stream-events";

export type StateType = { messages: Message[]; ui?: UIMessage[] };

// 扩展的上下文类型，包含查询上下文
export type ExtendedStreamContextType = StreamContextType & {
  queryContext: QueryContext;
  resetQueryContext: () => void;
};

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
      context?: Record<string, unknown>;
    };
    CustomEventType: UIMessage | RemoveUIMessage;
  }
>;

// 使用 UseStream 类型（包含完整的 getMessagesMetadata, setBranch 等方法）
// 而不是 ReturnType<typeof useTypedStream>（TypeScript 会推断为 UseStreamCustom，缺少这些方法）
type BagType = {
  UpdateType: {
    messages?: Message[] | Message | string;
    ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
    context?: Record<string, unknown>;
  };
  CustomEventType: UIMessage | RemoveUIMessage;
};
type StreamContextType = UseStream<StateType, BagType>;
const StreamContext = createContext<ExtendedStreamContextType | undefined>(undefined);

async function sleep(ms = 4000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkGraphStatus(
  apiUrl: string,
  apiKey: string | null,
): Promise<boolean> {
  try {
    const res = await fetch(`${apiUrl}/info`, {
      ...(apiKey && {
        headers: {
          "X-Api-Key": apiKey,
        },
      }),
    });

    return res.ok;
  } catch (e) {
    console.error(e);
    return false;
  }
}

const StreamSession = ({
  children,
  apiKey,
  apiUrl,
  assistantId,
}: {
  children: ReactNode;
  apiKey: string | null;
  apiUrl: string;
  assistantId: string;
}) => {
  const [threadId, setThreadId] = useQueryState("threadId");
  const { getThreads, setThreads } = useThreads();
  
  // 查询上下文状态 - 用于存储流式事件数据
  const [queryContext, setQueryContext] = useState<QueryContext>(createEmptyQueryContext());
  
  // 同步跟踪已处理的 SQL 步骤，避免状态更新异步导致的重复添加
  const processedStepsRef = useRef<Set<string>>(new Set());
  
  // 重置查询上下文
  const resetQueryContext = useCallback(() => {
    setQueryContext(createEmptyQueryContext());
    // 清空已处理步骤记录
    processedStepsRef.current.clear();
  }, []);
  
  const streamValue = useTypedStream({
    apiUrl,
    apiKey: apiKey ?? undefined,
    assistantId,
    threadId: threadId ?? null,
    fetchStateHistory: true,
    onCustomEvent: (event, options) => {
      // 处理 UI 消息
      if (isUIMessage(event) || isRemoveUIMessage(event)) {
        options.mutate((prev) => {
          const ui = uiMessageReducer(prev.ui ?? [], event);
          return { ...prev, ui };
        });
        return;
      }
      
      // 处理流式事件
      if (isStreamEvent(event)) {
        const streamEvent = event as StreamEvent;
        switch (streamEvent.type) {
          case "cache_hit":
            // 缓存命中事件
            setQueryContext(prev => ({
              ...prev,
              cacheHit: streamEvent
            }));
            break;
            
          case "intent_analysis":
            setQueryContext(prev => ({
              ...prev,
              intentAnalysis: streamEvent
            }));
            break;
            
          case "sql_step":
            // 使用同步去重标记防止重复处理
            const stepSignature = `${streamEvent.step}-${streamEvent.status}-${streamEvent.time_ms || 0}`;
            
            // 对所有状态进行去重检查
            if (processedStepsRef.current.has(stepSignature)) {
              return; // 跳过重复事件
            }
            
            // 立即标记为已处理（在状态更新前）
            processedStepsRef.current.add(stepSignature);
            
            setQueryContext(prev => {
              // 更新或添加步骤
              const existingIndex = prev.sqlSteps.findIndex(
                s => s.step === streamEvent.step
              );
              
              if (existingIndex >= 0) {
                // 检查是否真的有变化，避免不必要的更新
                const existing = prev.sqlSteps[existingIndex];
                if (
                  existing.status === streamEvent.status &&
                  existing.result === streamEvent.result &&
                  existing.time_ms === streamEvent.time_ms
                ) {
                  return prev; // 没有变化，返回原状态
                }
                
                // 更新现有步骤
                const newSteps = [...prev.sqlSteps];
                newSteps[existingIndex] = streamEvent;
                return { ...prev, sqlSteps: newSteps };
              } else {
                // 添加新步骤
                return { ...prev, sqlSteps: [...prev.sqlSteps, streamEvent] };
              }
            });
            break;
            
          case "data_query":
            setQueryContext(prev => ({
              ...prev,
              dataQuery: streamEvent
            }));
            break;
            
          case "similar_questions":
            setQueryContext(prev => ({
              ...prev,
              similarQuestions: streamEvent
            }));
            break;
        }
      }
    },
    onThreadId: (id) => {
      setThreadId(id);
      // 新对话时重置查询上下文
      resetQueryContext();
      // Refetch threads list when thread ID changes.
      // Wait for some seconds before fetching so we're able to get the new thread that was created.
      sleep().then(() => getThreads().then(setThreads).catch(console.error));
    },
    onFinish: (state, run) => {
      // Refetch threads list when stream finishes to update thread names
      // This ensures the thread list shows the proper conversation title instead of thread ID
      sleep(1000).then(() => getThreads().then(setThreads).catch(console.error));
    },
  });
  
  // 合并 streamValue 和 queryContext
  const extendedValue: ExtendedStreamContextType = {
    ...streamValue,
    queryContext,
    resetQueryContext,
  };

  useEffect(() => {
    checkGraphStatus(apiUrl, apiKey).then((ok) => {
      if (!ok) {
        toast.error("Failed to connect to LangGraph server", {
          description: () => (
            <p>
              Please ensure your graph is running at <code>{apiUrl}</code> and
              your API key is correctly set (if connecting to a deployed graph).
            </p>
          ),
          duration: 10000,
          richColors: true,
          closeButton: true,
        });
      }
    });
  }, [apiKey, apiUrl]);

  return (
    <StreamContext.Provider value={extendedValue}>
      {children}
    </StreamContext.Provider>
  );
};

// Default values for the form
const DEFAULT_API_URL = "http://localhost:2024";
const DEFAULT_ASSISTANT_ID = "agent";

export const StreamProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  // Get environment variables
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined =
    process.env.NEXT_PUBLIC_ASSISTANT_ID;

  // Use URL params with env var fallbacks
  const [apiUrl, setApiUrl] = useQueryState("apiUrl", {
    defaultValue: envApiUrl || "",
  });
  const [assistantId, setAssistantId] = useQueryState("assistantId", {
    defaultValue: envAssistantId || "",
  });

  // For API key, use localStorage with env var fallback
  const [apiKey, _setApiKey] = useState(() => {
    const storedKey = getApiKey();
    return storedKey || "";
  });

  const setApiKey = (key: string) => {
    window.localStorage.setItem("lg:chat:apiKey", key);
    _setApiKey(key);
  };

  // Determine final values to use, prioritizing URL params then env vars
  const finalApiUrl = apiUrl || envApiUrl;
  const finalAssistantId = assistantId || envAssistantId;

  // Show the form if we: don't have an API URL, or don't have an assistant ID
  if (!finalApiUrl || !finalAssistantId) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center p-4">
        <div className="animate-in fade-in-0 zoom-in-95 bg-background flex max-w-3xl flex-col rounded-lg border shadow-lg">
          <div className="mt-14 flex flex-col gap-2 border-b p-6">
            <div className="flex flex-col items-start gap-2">
              <LangGraphLogoSVG className="h-7" />
              <h1 className="text-xl font-semibold tracking-tight">
                任我行智能
              </h1>
            </div>
            <p className="text-muted-foreground">
              欢迎使用任我行智能！在开始之前，您需要输入部署的URL。
            </p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();

              const form = e.target as HTMLFormElement;
              const formData = new FormData(form);
              const apiUrl = formData.get("apiUrl") as string;
              const assistantId = formData.get("assistantId") as string;
              const apiKey = formData.get("apiKey") as string;

              setApiUrl(apiUrl);
              setApiKey(apiKey);
              setAssistantId(assistantId);

              form.reset();
            }}
            className="bg-muted/50 flex flex-col gap-6 p-6"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="apiUrl">
                部署URL<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                这是您的服务器端部署的URL。可以是本地或生产环境的部署。
              </p>
              <Input
                id="apiUrl"
                name="apiUrl"
                className="bg-background"
                defaultValue={apiUrl || DEFAULT_API_URL}
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="assistantId">
                助手/Graph ID<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                这是Graph的ID（可以是Graph名称）或助手的ID，用于获取对话线程并在执行操作时调用。
              </p>
              <Input
                id="assistantId"
                name="assistantId"
                className="bg-background"
                defaultValue={assistantId || DEFAULT_ASSISTANT_ID}
                required
              />
            </div>

            <div className="mt-2 flex justify-end">
              <Button
                type="submit"
                size="lg"
              >
                继续
                <ArrowRight className="size-5" />
              </Button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <StreamSession
      apiKey={apiKey}
      apiUrl={apiUrl}
      assistantId={assistantId}
    >
      {children}
    </StreamSession>
  );
};

// Create a custom hook to use the context
export const useStreamContext = (): ExtendedStreamContextType => {
  const context = useContext(StreamContext);
  if (context === undefined) {
    throw new Error("useStreamContext must be used within a StreamProvider");
  }

  // Ensure messages is always an array to prevent filter errors
  // Add extra safety for cross-platform compatibility
  const safeMessages = Array.isArray(context.messages) ? context.messages : [];

  return {
    ...context,
    messages: safeMessages,
  };
};

export default StreamContext;
