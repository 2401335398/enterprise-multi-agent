import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createSession,
  loadApiKey,
  loadSessions,
  requestSessionId,
  saveApiKey,
  saveSessions,
  sessionTitle,
} from "./storage";

describe("session storage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("round-trips chat sessions", () => {
    const session = createSession();
    saveSessions([session]);
    expect(loadSessions()).toEqual([session]);
  });

  it("keeps the API key in session storage", () => {
    saveApiKey("  demo-secret  ");
    expect(loadApiKey()).toBe("demo-secret");
    expect(localStorage.length).toBe(0);
  });

  it("creates a compact title", () => {
    expect(sessionTitle("  分析   下一季度的产品机会  ")).toBe("分析 下一季度的产品机会");
    expect(sessionTitle("a".repeat(40))).toBe(`${"a".repeat(28)}...`);
  });

  it("uses the local session id until the backend id is known", () => {
    const session = createSession();
    expect(requestSessionId(session)).toBe(session.id);

    session.backendSessionId = "alice:backend-session";
    expect(requestSessionId(session)).toBe("alice:backend-session");
  });

  it("falls back to compact history when detailed responses exceed storage", () => {
    const session = createSession();
    session.backendSessionId = "alice:persistent-session";
    session.messages.push({
      id: "m1",
      role: "assistant",
      content: "仍然保留的回答",
      createdAt: Date.now(),
      response: {
        session_id: "alice:persistent-session",
        answer: "仍然保留的回答",
        task_type: "complex",
        tasks: [],
        trace: [],
        structured_trace: [{ event_type: "large-trace" }],
        errors: [],
        metrics: {
          workflow_id: "w1",
          latency_ms: 1,
          total_retries: 0,
          total_llm_calls: 1,
          total_input_tokens: 1,
          total_output_tokens: 1,
          total_tool_calls: 0,
          memory_extractor_calls: 0,
          memory_consolidator_calls: 0,
          memory_fast_path_skips: 1,
          estimated_cost_usd: 0,
        },
      },
    });

    const originalSetItem = Storage.prototype.setItem;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (
      this: Storage,
      key: string,
      value: string,
    ) {
      if (value.includes("structured_trace")) {
        throw new DOMException("Quota exceeded", "QuotaExceededError");
      }
      originalSetItem.call(this, key, value);
    });

    saveSessions([session]);

    const restored = loadSessions();
    expect(restored[0].backendSessionId).toBe("alice:persistent-session");
    expect(restored[0].messages[0].content).toBe("仍然保留的回答");
    expect(restored[0].messages[0].response).toBeUndefined();
  });
});
