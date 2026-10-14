import { describe, expect, it } from "vitest";
import { extractEvidenceSources, linkifyCitations } from "./sources";
import type { ChatResponse } from "./types";

const response = {
  tasks: [
    {
      id: "T1",
      tool_results: [
        {
          tool: "document_search",
          success: true,
          result: {
            results: [
              {
                text: "KnowledgeFlow serves manufacturing teams.",
                metadata: { file_name: "strategy.pdf", page: 3, chunk_id: "c1" },
              },
              {
                text: "The product includes a copilot.",
                metadata: { file_name: "release.txt", chunk_id: "c2" },
              },
            ],
          },
        },
      ],
    },
  ],
} as unknown as ChatResponse;

describe("evidence sources", () => {
  it("extracts document metadata from tool results", () => {
    expect(extractEvidenceSources(response)).toEqual([
      expect.objectContaining({ number: 1, fileName: "strategy.pdf", page: 3, excerpt: "KnowledgeFlow serves manufacturing teams." }),
      expect.objectContaining({ number: 2, fileName: "release.txt", excerpt: "The product includes a copilot." }),
    ]);
  });

  it("turns available citations into anchors", () => {
    const sources = extractEvidenceSources(response);
    expect(linkifyCitations("Fact [Source 1], missing [Source 9].", "m-1", sources)).toBe(
      "Fact [strategy.pdf · 第 3 页](#source-m-1-1), missing [Source 9].",
    );
  });
});
