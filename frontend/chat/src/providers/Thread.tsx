
import { validate } from "uuid";
import { getApiKey } from "@/lib/api-key";
import { Thread } from "@langchain/langgraph-sdk";
import { useQueryState } from "nuqs";
import {
  createContext,
  useContext,
  ReactNode,
  useCallback,
  useState,
  useEffect,
  Dispatch,
  SetStateAction,
} from "react";
import { createClient } from "./client";
import { getLangGraphApiUrl, getBackendApiUrl } from "@/utils/apiConfig";

// 轻量级 Thread 摘要类型
interface ThreadSummary {
  thread_id: string;
  created_at?: string;
  updated_at?: string;
  status?: string;
  first_message?: string;
  metadata?: Record<string, unknown>;
}

// 分页响应类型
interface ThreadSearchResponse {
  threads: ThreadSummary[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// 将 ThreadSummary 转换为 Thread 类型以兼容现有代码
function summaryToThread(summary: ThreadSummary): Thread {
  return {
    thread_id: summary.thread_id,
    created_at: summary.created_at || new Date().toISOString(),
    updated_at: summary.updated_at || new Date().toISOString(),
    status: summary.status || "idle",
    metadata: summary.metadata || {},
    values: summary.first_message ? {
      messages: [{ content: summary.first_message }]
    } : {},
  } as Thread;
}

interface ThreadContextType {
  getThreads: () => Promise<Thread[]>;
  threads: Thread[];
  setThreads: Dispatch<SetStateAction<Thread[]>>;
  threadsLoading: boolean;
  setThreadsLoading: Dispatch<SetStateAction<boolean>>;
  deleteThread: (threadId: string) => Promise<void>;
}

const ThreadContext = createContext<ThreadContextType | undefined>(undefined);

function getThreadSearchMetadata(
  assistantId: string,
): { graph_id: string } | { assistant_id: string } {
  if (validate(assistantId)) {
    return { assistant_id: assistantId };
  } else {
    return { graph_id: assistantId };
  }
}

export function ThreadProvider({ children }: { children: ReactNode }) {
  // 动态获取 LangGraph API URL
  const [dynamicApiUrl, setDynamicApiUrl] = useState<string>("");
  
  // 客户端初始化时获取动态 URL
  useEffect(() => {
    setDynamicApiUrl(getLangGraphApiUrl());
  }, []);

  // Get environment variables
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined = process.env.NEXT_PUBLIC_ASSISTANT_ID;

  // Use URL params with env var fallbacks
  const [apiUrl] = useQueryState("apiUrl", {
    defaultValue: envApiUrl || "",
  });
  const [assistantId] = useQueryState("assistantId", {
    defaultValue: envAssistantId || "",
  });

  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);

  // Determine final values to use
  // 优先级：1. URL 参数 2. 动态检测的 URL（根据访问地址自动切换）3. 环境变量
  const finalApiUrl = apiUrl || dynamicApiUrl || envApiUrl;
  const finalAssistantId = assistantId || envAssistantId;

  const getThreads = useCallback(async (): Promise<Thread[]> => {
    if (!finalAssistantId) return [];
    
    try {
      // 使用后端分页代理接口，避免 LangGraph 返回数据过大
      const backendUrl = getBackendApiUrl();
      const response = await fetch(`${backendUrl}/threads/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          metadata: getThreadSearchMetadata(finalAssistantId),
          limit: 50,
          offset: 0,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch threads: ${response.status}`);
      }

      const data: ThreadSearchResponse = await response.json();
      return data.threads.map(summaryToThread);
    } catch (error) {
      console.error("Error fetching threads:", error);
      return [];
    }
  }, [finalAssistantId]);

  const deleteThread = useCallback(async (threadId: string): Promise<void> => {
    try {
      // 使用后端代理接口删除 thread
      const backendUrl = getBackendApiUrl();
      const response = await fetch(`${backendUrl}/threads/${threadId}`, {
        method: "DELETE",
      });

      if (!response.ok && response.status !== 404) {
        throw new Error(`Failed to delete thread: ${response.status}`);
      }

      // Remove the thread from local state
      setThreads(prevThreads => prevThreads.filter(thread => thread.thread_id !== threadId));
    } catch (error) {
      console.error("Error deleting thread:", error);
      throw error;
    }
  }, []);

  const value = {
    getThreads,
    threads,
    setThreads,
    threadsLoading,
    setThreadsLoading,
    deleteThread,
  };

  return (
    <ThreadContext.Provider value={value}>{children}</ThreadContext.Provider>
  );
}

export function useThreads() {
  const context = useContext(ThreadContext);
  if (context === undefined) {
    throw new Error("useThreads must be used within a ThreadProvider");
  }
  return context;
}
