import { MessageSquare, PanelLeftClose, Plus, Trash2 } from "lucide-react";
import type { ChatSession } from "../types";

interface SidebarProps {
  sessions: ChatSession[];
  activeId: string;
  open: boolean;
  disabled: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}

export function Sidebar({
  sessions,
  activeId,
  open,
  disabled,
  onClose,
  onSelect,
  onCreate,
  onDelete,
}: SidebarProps) {
  const sorted = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt);

  return (
    <aside className={`sidebar ${open ? "sidebar--open" : ""}`} aria-label="会话列表">
      <div className="sidebar__header">
        <div className="brand-mark" aria-hidden="true">EI</div>
        <div className="brand-copy">
          <strong>Enterprise Intelligence</strong>
          <span>Multi-Agent Workspace</span>
        </div>
        <button className="icon-button sidebar__close" onClick={onClose} aria-label="关闭会话列表">
          <PanelLeftClose size={18} />
        </button>
      </div>

      <button className="new-chat-button" onClick={onCreate} disabled={disabled}>
        <Plus size={17} />
        新建会话
      </button>

      <div className="session-list">
        <div className="session-list__label">最近会话</div>
        {sorted.map((session) => (
          <div
            className={`session-row ${session.id === activeId ? "session-row--active" : ""}`}
            key={session.id}
          >
            <button
              className="session-row__select"
              onClick={() => onSelect(session.id)}
              disabled={disabled}
              aria-current={session.id === activeId ? "page" : undefined}
            >
              <MessageSquare size={16} />
              <span>
                <strong>{session.title}</strong>
                <small>{formatSessionTime(session.updatedAt)}</small>
              </span>
            </button>
            <button
              className="session-row__delete"
              onClick={() => onDelete(session.id)}
              disabled={disabled}
              aria-label={`删除会话 ${session.title}`}
              title="删除会话"
            >
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}

function formatSessionTime(timestamp: number): string {
  const date = new Date(timestamp);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}
