import type { ChatSession } from "./types";

const SESSION_KEY = "enterprise-agent.sessions.v1";
const ACTIVE_KEY = "enterprise-agent.active-session.v1";
const API_KEY = "enterprise-agent.api-key.v1";

export function createSession(): ChatSession {
  const now = Date.now();
  return {
    id: crypto.randomUUID(),
    backendSessionId: null,
    title: "新会话",
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

export function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return [];
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];

    return value.filter(
      (item): item is ChatSession =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as ChatSession).id === "string" &&
        Array.isArray((item as ChatSession).messages),
    );
  } catch {
    return [];
  }
}

export function saveSessions(sessions: ChatSession[]): void {
  const compact = (items: ChatSession[]): ChatSession[] =>
    items.map((session) => ({
      ...session,
      messages: session.messages.map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        createdAt: message.createdAt,
      })),
    }));

  const candidates = [
    sessions.slice(0, 20),
    sessions.slice(0, 5),
    compact(sessions.slice(0, 20)),
    compact(sessions.slice(0, 5)),
  ];

  for (const candidate of candidates) {
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify(candidate));
      return;
    } catch {
      // Try a smaller or trace-free representation next.
    }
  }
}

export function requestSessionId(session: ChatSession): string {
  return session.backendSessionId ?? session.id;
}

export function loadActiveSessionId(): string | null {
  return localStorage.getItem(ACTIVE_KEY);
}

export function saveActiveSessionId(id: string): void {
  localStorage.setItem(ACTIVE_KEY, id);
}

export function loadApiKey(): string {
  return sessionStorage.getItem(API_KEY) ?? "";
}

export function saveApiKey(value: string): void {
  if (value.trim()) sessionStorage.setItem(API_KEY, value.trim());
  else sessionStorage.removeItem(API_KEY);
}

export function sessionTitle(message: string): string {
  const normalized = message.replace(/\s+/g, " ").trim();
  return normalized.length > 28 ? `${normalized.slice(0, 28)}...` : normalized;
}
