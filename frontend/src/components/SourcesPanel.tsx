import { BookOpen, ChevronDown, FileText } from "lucide-react";
import type { EvidenceSource } from "../types";
import { sourceAnchorId } from "../sources";

interface SourcesPanelProps {
  messageId: string;
  sources: EvidenceSource[];
}

export function SourcesPanel({ messageId, sources }: SourcesPanelProps) {
  if (sources.length === 0) return null;

  return (
    <section className="sources-panel" aria-labelledby={`sources-title-${messageId}`}>
      <div className="sources-panel__heading">
        <span className="sources-panel__icon"><BookOpen size={16} /></span>
        <div>
          <h3 id={`sources-title-${messageId}`}>证据来源</h3>
          <p>{sources.length} 条知识库检索片段</p>
        </div>
      </div>

      <div className="source-list">
        {sources.map((source, index) => {
          const isFirstNumber = sources.findIndex((item) => item.number === source.number) === index;
          return (
            <details
              className="source-item"
              id={isFirstNumber ? sourceAnchorId(messageId, source.number) : undefined}
              key={`${source.key}-${index}`}
            >
              <summary>
                <span className="source-item__number">{source.number}</span>
                <span className="source-item__identity">
                  <strong><FileText size={14} />{source.fileName}</strong>
                  <small>
                    {source.page != null ? `第 ${source.page} 页` : "文本资料"}
                    {source.taskId ? ` · ${source.taskId}` : ""}
                  </small>
                </span>
                <ChevronDown size={16} className="source-item__chevron" />
              </summary>
              <div className="source-item__excerpt">{source.excerpt}</div>
            </details>
          );
        })}
      </div>
    </section>
  );
}
