import { Client, ThreadState } from "@langchain/langgraph-sdk";
import { LangChainMessage } from "@assistant-ui/react-langgraph";
import { getLangGraphApiUrl } from "@/utils/apiConfig";

let cachedClient: Client | null = null;
let cachedApiUrl: string | null = null;
let cachedApiKey: string | null = null;

function getClient(apiUrl?: string, apiKey?: string | null): Client {
  // 动态获取 URL，支持 localhost 和局域网 IP
  const getDynamicUrl = () => {
    if (typeof window === 'undefined') {
      return process.env.NEXT_PUBLIC_API_URL || "/api";
    }
    return getLangGraphApiUrl();
  };
  
  const url = apiUrl || getDynamicUrl();
  const key = apiKey ?? null;

  // Return cached client if config hasn't changed
  if (cachedClient && cachedApiUrl === url && cachedApiKey === key) {
    return cachedClient;
  }

  cachedApiUrl = url;
  cachedApiKey = key;
  cachedClient = new Client({
    apiUrl: url,
    apiKey: key ?? undefined,
  });

  return cachedClient;
}

export interface ChatApiConfig {
  apiUrl?: string;
  apiKey?: string | null;
  assistantId?: string;
}

export interface SendMessageParams {
  threadId: string;
  messages: LangChainMessage[];
  config?: ChatApiConfig;
}

export async function createThread(config?: ChatApiConfig) {
  const client = getClient(config?.apiUrl, config?.apiKey);
  return client.threads.create();
}

export async function getThreadState(
  threadId: string,
  config?: ChatApiConfig
): Promise<ThreadState<{ messages: LangChainMessage[] }>> {
  const client = getClient(config?.apiUrl, config?.apiKey);
  return client.threads.getState(threadId);
}

export async function sendMessage(params: SendMessageParams) {
  const client = getClient(params.config?.apiUrl, params.config?.apiKey);
  const assistantId =
    params.config?.assistantId ||
    process.env.NEXT_PUBLIC_ASSISTANT_ID ||
    "agent";

  return client.runs.stream(params.threadId, assistantId, {
    input: {
      messages: params.messages,
    },
    streamMode: ["values", "custom"],
    streamSubgraphs: true,
  });
}

export async function deleteThread(
  threadId: string,
  config?: ChatApiConfig
): Promise<void> {
  const client = getClient(config?.apiUrl, config?.apiKey);
  await client.threads.delete(threadId);
}

export async function listThreads(config?: ChatApiConfig) {
  const client = getClient(config?.apiUrl, config?.apiKey);
  const assistantId =
    config?.assistantId || process.env.NEXT_PUBLIC_ASSISTANT_ID || "agent";

  return client.threads.search({
    metadata: {
      graph_id: assistantId,
    },
    limit: 100,
  });
}
