import {
  Activity,
  Bot,
  ChevronDown,
  CircleCheck,
  CircleX,
  Clock3,
  Coins,
  Network,
  RotateCcw,
  Wrench,
} from "lucide-react";
import type { AgentTask, ChatResponse } from "../types";

interface RunDetailsProps {
  response: ChatResponse;
}

export function RunDetails({ response }: RunDetailsProps) {
  const { metrics, tasks, trace, errors } = response;
  const totalTokens = metrics.total_input_tokens + metrics.total_output_tokens;

  return (
    <details className="run-details">
      <summary>
        <span><Activity size={16} />运行详情</span>
        <span className="run-details__summary">
          {response.task_type || "workflow"} · {tasks.length} 个任务 · {formatDuration(metrics.latency_ms)}
          <ChevronDown size={16} className="details-chevron" />
        </span>
      </summary>

      <div className="metrics-grid">
        <Metric icon={<Clock3 size={16} />} label="总耗时" value={formatDuration(metrics.latency_ms)} />
        <Metric icon={<Coins size={16} />} label="Token" value={totalTokens.toLocaleString()} />
        <Metric icon={<Bot size={16} />} label="LLM 调用" value={String(metrics.total_llm_calls)} />
        <Metric icon={<Wrench size={16} />} label="工具调用" value={String(metrics.total_tool_calls)} />
        <Metric icon={<RotateCcw size={16} />} label="重试" value={String(metrics.total_retries)} />
        <Metric
          icon={<Coins size={16} />}
          label="估算成本"
          value={`$${metrics.estimated_cost_usd.toFixed(6)}`}
        />
        <Metric
          icon={<Network size={16} />}
          label="工作流"
          value={shortId(metrics.workflow_id)}
          title={metrics.workflow_id}
        />
      </div>

      {tasks.length > 0 && (
        <section className="detail-section">
          <h4>任务执行</h4>
          <div className="task-list">
            {tasks.map((task, index) => (
              <TaskRow task={task} index={index} key={task.id ?? index} />
            ))}
          </div>
        </section>
      )}

      {trace.length > 0 && (
        <section className="detail-section">
          <h4>执行轨迹</h4>
          <ol className="trace-list">
            {trace.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
          </ol>
        </section>
      )}

      {errors.length > 0 && (
        <section className="detail-section detail-section--error">
          <h4>异常</h4>
          {errors.map((error, index) => <p key={`${index}-${error}`}>{error}</p>)}
        </section>
      )}
    </details>
  );
}

function Metric({
  icon,
  label,
  value,
  title,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <div className="metric" title={title}>
      <span className="metric__icon">{icon}</span>
      <span><small>{label}</small><strong>{value}</strong></span>
    </div>
  );
}

function TaskRow({ task, index }: { task: AgentTask; index: number }) {
  const complete = task.status === "completed";
  const tools = task.tool_calls
    ?.map((call) => call.tool)
    .filter((tool): tool is string => Boolean(tool));

  return (
    <div className="task-row">
      <div className={`task-row__status ${complete ? "is-success" : "is-error"}`}>
        {complete ? <CircleCheck size={17} /> : <CircleX size={17} />}
      </div>
      <div className="task-row__content">
        <div className="task-row__topline">
          <strong>{task.id ?? `T${index + 1}`} · {task.agent ?? "agent"}</strong>
          <span>{task.latency_ms != null ? formatDuration(task.latency_ms) : task.status}</span>
        </div>
        <p>{task.description ?? "未提供任务描述"}</p>
        <div className="task-row__tags">
          {task.skill && <span>{task.skill}</span>}
          {tools?.map((tool) => <span key={tool}>{tool}</span>)}
        </div>
        {task.error && <div className="task-row__error">{task.error}</div>}
      </div>
    </div>
  );
}

function formatDuration(milliseconds: number): string {
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`;
  return `${(milliseconds / 1000).toFixed(1)} s`;
}

function shortId(value: string): string {
  return value ? `${value.slice(0, 8)}...` : "-";
}
