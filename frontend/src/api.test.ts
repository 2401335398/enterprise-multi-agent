import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getHealth, sendChat } from "./api";
import type { ChatResponse } from "./types";

const response: ChatResponse = {
  session_id: "alice:s1",
  answer: "answer",
  task_type: "simple",
  tasks: [],
  trace: [],
  structured_trace: [],
  errors: [],
  metrics: {
    workflow_id: "w1",
    latency_ms: 10,
    total_retries: 0,
    total_llm_calls: 1,
    total_input_tokens: 10,
    total_output_tokens: 5,
    total_tool_calls: 0,
    memory_extractor_calls: 0,
    memory_consolidator_calls: 0,
    memory_fast_path_skips: 1,
    estimated_cost_usd: 0,
  },
};

describe("API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads backend health", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", mode: "dev" }), { status: 200 }),
    ));
    await expect(getHealth()).resolves.toEqual({ status: "ok", mode: "dev" });
  });

  it("sends the session and API key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await sendChat("hello", "alice:s1", "secret", new AbortController().signal);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-API-Key": "secret" }),
        body: JSON.stringify({ message: "hello", session_id: "alice:s1" }),
      }),
    );
  });

  it("maps unauthorized responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "invalid" }), { status: 401 }),
    ));

    await expect(getHealth()).rejects.toMatchObject({
      status: 401,
      message: "API Key 缺失或无效，请检查连接设置。",
    } satisfies Partial<ApiError>);
  });
});
