/**
 * Stream Provider
 * 提供 LangGraph 流式通信上下文
 * 
 * 模块结构：
 * - stream/types.ts: 类型定义
 * - stream/utils.ts: 辅助函数
 */

import React, {
  createContext,
  useContext,
  ReactNode,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
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
import { getApiKey } from "@/lib/api-key";
import { useThreads } from "./Thread";
import { toast } from "sonner";
import {
  type QueryContext,
  type StreamEvent,
  createEmptyQueryContext,
  isStreamEvent,
} from "@/types/stream-events";

// 从拆分模块导入类型和辅助函数
import {
  type StateType,
  type ExtendedStreamContextType,
} from "./stream/types";
import {
  sleep,
  checkGraphStatus,
  getStorageKey,
  getDefaultApiUrl,
  DEFAULT_ASSISTANT_ID,
} from "./stream/utils";
import { getLangGraphApiUrl } from "@/utils/apiConfig";

// 重新导出类型，保持向后兼容
export type { StateType, ExtendedStreamContextType } from "./stream/types";

// 创建类型化的 useStream hook
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

import { type Message } from "@langchain/langgraph-sdk";

const StreamContext = createContext<ExtendedStreamContextType | undefined>(undefined);

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
  
  // 保存 queryContext 到 localStorage
  const saveQueryContextToStorage = useCallback((tid: string | null, ctx: QueryContext) => {
    if (!tid) return;
    
    // 只有在有实际数据时才保存
    const hasData = ctx.sqlSteps.length > 0 || ctx.stageMessages.length > 0 || ctx.dataQuery || ctx.intentAnalysis || ctx.cacheHit;
    if (hasData) {
      try {
        localStorage.setItem(getStorageKey(tid), JSON.stringify(ctx));
      } catch (e) {
        console.warn("Failed to save queryContext to localStorage:", e);
      }
    }
  }, []);
  
  // 从 localStorage 恢复 queryContext
  const loadQueryContextFromStorage = useCallback((tid: string | null): QueryContext | null => {
    if (!tid) return null;
    
    try {
      const stored = localStorage.getItem(getStorageKey(tid));
      if (stored) {
        const parsed = JSON.parse(stored) as QueryContext;
        return {
          ...parsed,
          sqlSteps: parsed.sqlSteps ?? [],
          stageMessages: parsed.stageMessages ?? []
        };
      }
    } catch (e) {
      console.warn("Failed to load queryContext from localStorage:", e);
    }
    return null;
  }, []);
  
  // 重置查询上下文
  const resetQueryContext = useCallback(() => {
    setQueryContext(createEmptyQueryContext());
    // 清空已处理步骤记录
    processedStepsRef.current.clear();
  }, []);
  
  // 页面加载时，尝试从 localStorage 恢复 queryContext
  useEffect(() => {
    if (threadId) {
      const stored = loadQueryContextFromStorage(threadId);
      if (stored) {
        setQueryContext(stored);
        // 恢复已处理步骤的签名，避免后续重复处理
        stored.sqlSteps.forEach(step => {
          const signature = `${step.step}-${step.status}-${step.time_ms || 0}`;
          processedStepsRef.current.add(signature);
        });
      }
    }
  }, [threadId, loadQueryContextFromStorage]);
  
  // 当 queryContext 更新时，保存到 localStorage（使用防抖）
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      saveQueryContextToStorage(threadId, queryContext);
    }, 500); // 500ms 防抖，减少频繁写入
    
    return () => clearTimeout(timeoutId);
  }, [queryContext, threadId, saveQueryContextToStorage]);
  
  const streamValue = useTypedStream({
    apiUrl,
    apiKey: apiKey ?? undefined,
    assistantId,
    threadId: threadId ?? null,
    fetchStateHistory: true,  // 恢复历史消息，custom 事件通过 localStorage 恢复
    // 增加错误处理配置，忽略中断错误
    onError: (e: unknown) => {
      // 忽略用户主动中止或网络连接中断导致的错误
      const error = e as Error & { name?: string; message?: string };
      if (
        error.name === 'AbortError' || 
        error.message?.includes('The user aborted a request') ||
        error.message?.includes('net::ERR_ABORTED') ||
        error.message?.includes('Failed to fetch')
      ) {
        console.log('Stream aborted or connection interrupted (ignored)');
        // 不向上传递错误，避免 UI 闪烁
        return;
      }
      console.error("Stream error:", e);
    },
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
            
          case "sql_step": {
            // 使用更完整的签名进行去重，包含结果内容的前缀
            // 修复 (2026-01-23): 改进签名生成，避免不同结果的事件被错误跳过
            const resultPrefix = streamEvent.result ? streamEvent.result.substring(0, 50) : '';
            const stepSignature = `${streamEvent.step}-${streamEvent.status}-${resultPrefix}-${streamEvent.time_ms || 0}`;
            
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
          }
          case "stage_message": {
            setQueryContext(prev => ({
              ...prev,
              stageMessages: [...prev.stageMessages, streamEvent]
            }));
            break;
          }
            
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
            
          case "insight":
            // 数据洞察事件
            setQueryContext(prev => ({
              ...prev,
              insight: streamEvent
            }));
            break;
            
          case "thought":
            // 思维过程事件
            setQueryContext(prev => ({
              ...prev,
              thoughts: [...prev.thoughts, streamEvent]
            }));
            break;
            
          case "node_status":
            // 节点状态事件（用于错误恢复等场景）
            setQueryContext(prev => ({
              ...prev,
              nodeStatus: streamEvent
            }));
            // 如果是重试状态，可以显示 toast 通知用户
            if (streamEvent.status === "retrying" && streamEvent.message) {
              toast.info(streamEvent.message, {
                duration: 3000,
              });
            }
            break;
        }
      }
    },
    onThreadId: (id) => {
      setThreadId(id);
      // 新对话时重置查询上下文（新 threadId 意味着新对话）
      resetQueryContext();
      // Refetch threads list when thread ID changes.
      // Wait for some seconds before fetching so we're able to get the new thread that was created.
      sleep().then(() => getThreads().then(setThreads).catch(console.error));
    },
    onFinish: (state, run) => {
      // 兜底清理：强制结束所有 running 状态的步骤
      // 防止后端漏发完成事件导致 UI 永久显示加载状态
      setQueryContext(prev => {
        const hasRunningSteps = prev.sqlSteps.some(s => s.status === "running");
        if (!hasRunningSteps) return prev;
        
        return {
          ...prev,
          sqlSteps: prev.sqlSteps.map(step => 
            step.status === "running" 
              ? { ...step, status: "completed" as const }
              : step
          )
        };
      });
      
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

export const StreamProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  // 动态获取 LangGraph API URL
  const [dynamicApiUrl, setDynamicApiUrl] = useState<string>("");
  
  // 客户端初始化时获取动态 URL
  useEffect(() => {
    setDynamicApiUrl(getLangGraphApiUrl());
  }, []);
  
  // Get environment variables
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined =
    process.env.NEXT_PUBLIC_ASSISTANT_ID;

  // Use URL params with env var fallbacks、动态获取的 URL 优先级更高
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

  // Determine final values to use
  // 优先级：1. URL 参数 2. 动态检测的 URL（根据访问地址自动切换）3. 环境变量
  // 这样可以同时支持 localhost 和局域网 IP 访问
  const finalApiUrl = apiUrl || dynamicApiUrl || envApiUrl;
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
                defaultValue={apiUrl || dynamicApiUrl || getDefaultApiUrl()}
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
      apiUrl={finalApiUrl}
      assistantId={finalAssistantId}
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
