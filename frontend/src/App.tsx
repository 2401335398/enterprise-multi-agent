import {
  Bot,
  CheckCircle2,
  CircleOff,
  Menu,
  RefreshCw,
  Send,
  Settings,
  Square,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, getHealth, sendChat } from "./api";
import { ChatMessageView } from "./components/ChatMessageView";
import { SettingsDialog } from "./components/SettingsDialog";
import { Sidebar } from "./components/Sidebar";
import {
  createSession,
  loadActiveSessionId,
  loadApiKey,
  loadSessions,
  requestSessionId,
  saveActiveSessionId,
  saveApiKey,
  saveSessions,
  sessionTitle,
} from "./storage";
import type { ChatMessage, ChatSession, ConnectionState } from "./types";

const SUGGESTIONS = [
  "总结企业知识库中的产品战略重点",
  "分析当前产品的市场机会与主要风险",
  "结合内部资料给出下一季度优先级建议",
];

function initializeWorkspace(): { sessions: ChatSession[]; activeId: string } {
  const saved = loadSessions();
  const sessions = saved.length > 0 ? saved : [createSession()];
  const preferred = loadActiveSessionId();
  const activeId = sessions.some((session) => session.id === preferred)
    ? preferred!
    : sessions[0].id;
  return { sessions, activeId };
}

export default function App() {
  const initial = useMemo(initializeWorkspace, []);
  const [sessions, setSessions] = useState(initial.sessions);
  const [activeId, setActiveId] = useState(initial.activeId);
  const [draft, setDraft] = useState("");
  const [apiKey, setApiKey] = useState(loadApiKey);
  const [connection, setConnection] = useState<ConnectionState>({ status: "checking" });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [pending, setPending] = useState<{ sessionId: string; controller: AbortController } | null>(null);
  const messageEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const activeSession = sessions.find((session) => session.id === activeId) ?? sessions[0];

  useEffect(() => saveSessions(sessions), [sessions]);
  useEffect(() => saveActiveSessionId(activeId), [activeId]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeSession.messages, pending]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  }, [draft]);

  const checkConnection = useCallback(async () => {
    setConnection({ status: "checking" });
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 5000);
    try {
      const health = await getHealth(controller.signal);
      setConnection({ status: "online", mode: health.mode });
    } catch {
      setConnection({ status: "offline" });
    } finally {
      window.clearTimeout(timer);
    }
  }, []);

  useEffect(() => {
    void checkConnection();
    const interval = window.setInterval(() => void checkConnection(), 30_000);
    return () => window.clearInterval(interval);
  }, [checkConnection]);

  function updateSession(id: string, updater: (session: ChatSession) => ChatSession) {
    setSessions((current) => current.map((session) => (session.id === id ? updater(session) : session)));
  }

  function createNewSession() {
    if (pending) return;
    const session = createSession();
    setSessions((current) => [session, ...current]);
    setActiveId(session.id);
    setDraft("");
    setSidebarOpen(false);
    textareaRef.current?.focus();
  }

  function deleteSession(id: string) {
    if (pending || !window.confirm("删除这个本地会话记录？")) return;
    const remaining = sessions.filter((session) => session.id !== id);
    const next = remaining.length > 0 ? remaining : [createSession()];
    setSessions(next);
    if (activeId === id) setActiveId(next[0].id);
  }

  async function submitMessage(text = draft) {
    const message = text.trim();
    if (!message || pending || !activeSession) return;

    const targetId = activeSession.id;
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
      createdAt: Date.now(),
    };

    updateSession(targetId, (session) => ({
      ...session,
      title: session.messages.length === 0 ? sessionTitle(message) : session.title,
      updatedAt: Date.now(),
      messages: [...session.messages, userMessage],
    }));
    setDraft("");

    const controller = new AbortController();
    setPending({ sessionId: targetId, controller });

    try {
      const response = await sendChat(
        message,
        requestSessionId(activeSession),
        apiKey,
        controller.signal,
      );
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer || "本次执行没有返回文本答案。",
        createdAt: Date.now(),
        response,
      };

      updateSession(targetId, (session) => ({
        ...session,
        backendSessionId: response.session_id,
        updatedAt: Date.now(),
        messages: [...session.messages, assistantMessage],
      }));
    } catch (error) {
      const aborted = error instanceof DOMException && error.name === "AbortError";
      const content = aborted
        ? "已停止等待。后端任务可能仍在执行，请避免立即重复提交。"
        : formatError(error);
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "error",
        content,
        createdAt: Date.now(),
      };
      updateSession(targetId, (session) => ({
        ...session,
        updatedAt: Date.now(),
        messages: [...session.messages, errorMessage],
      }));
    } finally {
      setPending(null);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage();
    }
  }

  function handleSaveApiKey(value: string) {
    saveApiKey(value);
    setApiKey(value.trim());
    setSettingsOpen(false);
  }

  const isCurrentPending = pending?.sessionId === activeSession.id;

  return (
    <div className="app-shell">
      <Sidebar
        sessions={sessions}
        activeId={activeSession.id}
        open={sidebarOpen}
        disabled={Boolean(pending)}
        onClose={() => setSidebarOpen(false)}
        onSelect={(id) => { setActiveId(id); setSidebarOpen(false); }}
        onCreate={createNewSession}
        onDelete={deleteSession}
      />
      {sidebarOpen && <button className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-label="关闭会话列表" />}

      <main className="workspace">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="打开会话列表">
            <Menu size={20} />
          </button>
          <div className="topbar__title">
            <h1>{activeSession.title}</h1>
            {activeSession.backendSessionId && <span title={activeSession.backendSessionId}>会话已连接</span>}
          </div>
          <div className="topbar__actions">
            <ConnectionBadge state={connection} onRefresh={checkConnection} />
            <button className="icon-button" onClick={() => setSettingsOpen(true)} aria-label="API 设置" title="API 设置">
              <Settings size={19} />
            </button>
          </div>
        </header>

        <section className={`conversation ${activeSession.messages.length === 0 ? "conversation--empty" : ""}`} aria-live="polite">
          {activeSession.messages.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon"><Bot size={28} /></div>
              <h2>企业智能分析</h2>
              <p>内部知识、外部研究与综合决策</p>
              <div className="suggestion-list">
                {SUGGESTIONS.map((suggestion) => (
                  <button key={suggestion} onClick={() => void submitMessage(suggestion)} disabled={Boolean(pending)}>
                    <span>{suggestion}</span><Send size={15} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {activeSession.messages.map((message) => <ChatMessageView message={message} key={message.id} />)}
              {isCurrentPending && (
                <div className="working-state" role="status">
                  <span className="working-state__pulse" />
                  <div><strong>正在协调 Agent</strong><small>规划、检索和分析可能需要一些时间</small></div>
                </div>
              )}
              <div ref={messageEndRef} />
            </div>
          )}
        </section>

        <footer className="composer-wrap">
          <div className="composer">
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入需要检索或分析的问题..."
              rows={1}
              disabled={Boolean(pending)}
              aria-label="消息"
            />
            {pending ? (
              <button className="send-button send-button--stop" onClick={() => pending.controller.abort()} aria-label="停止等待" title="停止等待">
                <Square size={16} fill="currentColor" />
              </button>
            ) : (
              <button className="send-button" onClick={() => void submitMessage()} disabled={!draft.trim()} aria-label="发送消息" title="发送">
                <Send size={18} />
              </button>
            )}
          </div>
          <div className="composer-meta">
            <span>{apiKey ? "API Key 已设置" : "未设置 API Key"}</span>
          </div>
        </footer>
      </main>

      <SettingsDialog open={settingsOpen} apiKey={apiKey} onClose={() => setSettingsOpen(false)} onSave={handleSaveApiKey} />
    </div>
  );
}

function ConnectionBadge({ state, onRefresh }: { state: ConnectionState; onRefresh: () => Promise<void> }) {
  if (state.status === "checking") {
    return <span className="connection-badge"><RefreshCw size={14} className="spin" />连接中</span>;
  }

  return (
    <button
      className={`connection-badge connection-badge--${state.status}`}
      onClick={() => void onRefresh()}
      title="重新检查连接"
    >
      {state.status === "online" ? <CheckCircle2 size={14} /> : <CircleOff size={14} />}
      {state.status === "online" ? `${state.mode} · 在线` : "后端离线"}
    </button>
  );
}

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    const retry = error.retryAfter ? ` 请在 ${error.retryAfter} 秒后重试。` : "";
    return `${error.message}${retry}`;
  }
  if (error instanceof TypeError) return "无法连接后端服务，请检查服务是否已启动。";
  return error instanceof Error ? error.message : "请求失败，请稍后重试。";
}
