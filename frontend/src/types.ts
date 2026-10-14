export interface HealthResponse {
  status: string;
  mode: string;
}

export interface RuntimeMetrics {
  workflow_id: string;
  latency_ms: number;
  total_retries: number;
  total_llm_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tool_calls: number;
  memory_extractor_calls: number;
  memory_consolidator_calls: number;
  memory_fast_path_skips: number;
  estimated_cost_usd: number;
}

export interface AgentTask {
  id?: string;
  description?: string;
  agent?: string;
  status?: string;
  depends_on?: string[];
  skill?: string | null;
  latency_ms?: number | null;
  retry_count?: number;
  error?: string | null;
  tool_calls?: Array<{ tool?: string; arguments?: Record<string, unknown> }>;
  tool_results?: ToolExecutionResult[];
  [key: string]: unknown;
}

export interface RetrievalResult {
  text?: string;
  metadata?: {
    file_name?: string;
    page?: number | string;
    chunk_id?: string;
    document_id?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ToolExecutionResult {
  tool?: string;
  success?: boolean;
  result?: {
    original_query?: string;
    rewritten_query?: string;
    results?: RetrievalResult[];
    [key: string]: unknown;
  } | null;
  error?: string | null;
  [key: string]: unknown;
}

export interface EvidenceSource {
  key: string;
  number: number;
  fileName: string;
  page?: number | string;
  chunkId?: string;
  excerpt: string;
  taskId?: string;
}

export interface TraceEvent {
  event_type?: string;
  task_id?: string | null;
  agent?: string | null;
  success?: boolean;
  latency_ms?: number | null;
  [key: string]: unknown;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  task_type: string;
  tasks: AgentTask[];
  trace: string[];
  structured_trace: TraceEvent[];
  errors: string[];
  metrics: RuntimeMetrics;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  createdAt: number;
  response?: ChatResponse;
}

export interface ChatSession {
  id: string;
  backendSessionId: string | null;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}

export type ConnectionState =
  | { status: "checking" }
  | { status: "online"; mode: string }
  | { status: "offline" };
