
export function getApiKey(): string | null {
  try {
    if (typeof window === "undefined") return null;
    // 优先使用 auth_token (JWT token)，兼容旧的 lg:chat:apiKey
    return window.localStorage.getItem("auth_token") 
      ?? window.localStorage.getItem("lg:chat:apiKey") 
      ?? null;
  } catch {
    // no-op
  }

  return null;
}
