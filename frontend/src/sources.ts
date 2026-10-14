import type { ChatResponse, EvidenceSource } from "./types";

export function extractEvidenceSources(response: ChatResponse): EvidenceSource[] {
  const sources: EvidenceSource[] = [];
  const seen = new Set<string>();

  for (const task of response.tasks) {
    for (const toolResult of task.tool_results ?? []) {
      if (toolResult.tool !== "document_search" || !toolResult.success) continue;

      const results = toolResult.result?.results;
      if (!Array.isArray(results)) continue;

      results.forEach((result, index) => {
        const metadata = result.metadata ?? {};
        const excerpt = typeof result.text === "string" ? result.text.trim() : "";
        const fileName = metadata.file_name?.trim() || "未知文档";
        const identity = metadata.chunk_id || [fileName, metadata.page ?? "", excerpt].join(":");

        if (!excerpt || seen.has(identity)) return;
        seen.add(identity);
        sources.push({
          key: identity,
          number: index + 1,
          fileName,
          page: metadata.page,
          chunkId: metadata.chunk_id,
          excerpt,
          taskId: task.id,
        });
      });
    }
  }

  return sources;
}

export function sourceAnchorId(messageId: string, number: number): string {
  return `source-${messageId.replace(/[^a-zA-Z0-9_-]/g, "")}-${number}`;
}

export function linkifyCitations(
  content: string,
  messageId: string,
  sources: EvidenceSource[],
): string {
  const available = new Set(sources.map((source) => source.number));

  return content.replace(/\[Source\s+(\d+)\](?!\s*\()/gi, (match, rawNumber: string) => {
    const number = Number(rawNumber);
    if (!available.has(number)) return match;
    const source = sources.find((item) => item.number === number);
    if (!source) return match;
    const fileName = source.fileName.replaceAll("[", "").replaceAll("]", "");
    const location = source.page != null ? ` · 第 ${source.page} 页` : "";
    return `[${fileName}${location}](#${sourceAnchorId(messageId, number)})`;
  });
}
