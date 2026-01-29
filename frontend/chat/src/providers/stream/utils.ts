/**
 * Stream Provider 辅助函数
 */

/**
 * 异步等待指定毫秒数
 */
export async function sleep(ms = 4000): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * 检查 LangGraph 服务状态
 */
export async function checkGraphStatus(
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

/**
 * localStorage 相关常量和函数
 */
export const STORAGE_PREFIX = "chat-to-db:queryContext:";

/**
 * 生成 localStorage key
 */
export function getStorageKey(threadId: string): string {
  return `${STORAGE_PREFIX}${threadId}`;
}

/**
 * 默认表单值
 */
export const DEFAULT_API_URL = "http://localhost:2024";
export const DEFAULT_ASSISTANT_ID = "agent";
