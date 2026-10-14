import { AlertTriangle, Bot, UserRound } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../types";
import { extractEvidenceSources, linkifyCitations } from "../sources";
import { RunDetails } from "./RunDetails";
import { SourcesPanel } from "./SourcesPanel";

export function ChatMessageView({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <article className="message message--user">
        <div className="message__avatar"><UserRound size={17} /></div>
        <div className="message__body"><p>{message.content}</p></div>
      </article>
    );
  }

  if (message.role === "error") {
    return (
      <article className="message message--error" role="alert">
        <div className="message__avatar"><AlertTriangle size={17} /></div>
        <div className="message__body"><p>{message.content}</p></div>
      </article>
    );
  }

  const sources = message.response ? extractEvidenceSources(message.response) : [];
  const markdown = linkifyCitations(message.content, message.id, sources);

  return (
    <article className="message message--assistant">
      <div className="message__avatar"><Bot size={18} /></div>
      <div className="message__body">
        <div className="markdown-content">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: ({ href, children }) => (
                <a className={href?.startsWith("#source-") ? "citation-link" : undefined} href={href}>
                  {children}
                </a>
              ),
            }}
          >
            {markdown}
          </ReactMarkdown>
        </div>
        <SourcesPanel messageId={message.id} sources={sources} />
        {message.response && <RunDetails response={message.response} />}
      </div>
    </article>
  );
}
