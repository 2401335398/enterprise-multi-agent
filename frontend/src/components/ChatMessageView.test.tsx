import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ChatMessage } from "../types";
import { ChatMessageView } from "./ChatMessageView";

describe("ChatMessageView", () => {
  it("renders a real document citation and evidence excerpt", () => {
    const message = {
      id: "message-1",
      role: "assistant",
      content: "产品面向制造业客户 [Source 1]。",
      createdAt: 1,
      response: {
        session_id: "alice:s1",
        answer: "产品面向制造业客户 [Source 1]。",
        task_type: "knowledge",
        trace: [],
        structured_trace: [],
        errors: [],
        metrics: {
          workflow_id: "w1",
          latency_ms: 100,
          total_retries: 0,
          total_llm_calls: 1,
          total_input_tokens: 10,
          total_output_tokens: 5,
          total_tool_calls: 1,
          memory_extractor_calls: 0,
          memory_consolidator_calls: 0,
          memory_fast_path_skips: 1,
          estimated_cost_usd: 0,
        },
        tasks: [
          {
            id: "T1",
            status: "completed",
            agent: "knowledge",
            tool_results: [
              {
                tool: "document_search",
                success: true,
                result: {
                  results: [
                    {
                      text: "KnowledgeFlow 面向制造业客户。",
                      metadata: { file_name: "产品战略.pdf", page: 4, chunk_id: "chunk-1" },
                    },
                  ],
                },
              },
            ],
          },
        ],
      },
    } satisfies ChatMessage;

    render(<ChatMessageView message={message} />);

    expect(screen.getByRole("link", { name: "产品战略.pdf · 第 4 页" })).toHaveAttribute(
      "href",
      "#source-message-1-1",
    );
    expect(screen.getByText("KnowledgeFlow 面向制造业客户。")).toBeInTheDocument();
  });
});
