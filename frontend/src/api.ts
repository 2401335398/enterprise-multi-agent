import type { ChatResponse, HealthResponse } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly retryAfter?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let detail = "请求失败";

  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // Keep the generic error for non-JSON responses.
  }

  const messages: Record<number, string> = {
    401: "API Key 缺失或无效，请检查连接设置。",
    429: detail || "请求过于频繁，请稍后重试。",
    504: "任务执行超时，请缩小问题范围后重试。",
  };

  return new ApiError(
    messages[response.status] ?? `${detail}（HTTP ${response.status}）`,
    response.status,
    response.headers.get("Retry-After") ?? undefined,
  );
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`, { signal });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<HealthResponse>;
}

export async function sendChat(
  message: string,
  sessionId: string | null,
  apiKey: string,
  signal: AbortSignal,
): Promise<ChatResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (apiKey.trim()) headers["X-API-Key"] = apiKey.trim();

  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  });

  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<ChatResponse>;
}
