# Enterprise Multi-Agent Intelligence Platform

> 面向企业知识检索、外部研究与综合分析场景的多智能体协作系统  
> Core Principle: **LLM Planning + Deterministic Execution**

---

## 1. Project Overview

Enterprise Multi-Agent Intelligence Platform 是一个面向企业复杂知识任务的多智能体系统。

系统能够根据用户目标动态进行任务拆解，并生成带依赖关系的 Task DAG，由不同 Specialist Agent 分工完成企业内部知识检索、外部信息调研、综合分析与最终报告生成。

与完全依赖 LLM 自主控制执行流程的 Agent 系统不同，本项目采用：

> **LLM Planning + Deterministic Execution**

即：

- LLM 负责理解用户目标、拆解任务、分配 Agent、生成任务依赖；
- Deterministic Scheduler 负责真正的 DAG 调度、并发、超时、重试和状态合并。

系统同时集成：

- Multi-Agent Collaboration
- Dynamic Task DAG
- Hybrid RAG
- Semantic Memory
- Agent / Skill / Tool Routing
- MCP Tool Integration
- Tool Governance
- Structured Observability
- Token / Latency / Retry / Cost Tracking
- Langfuse Integration

---

## 2. Motivation

企业复杂知识任务通常并不是单一问答问题。

例如：

> “结合公司内部资料和外部市场情况，分析 KnowledgeFlow 下一季度的发展机会。”

这个问题同时涉及：

1. 企业内部知识检索；
2. 外部市场信息调研；
3. 多源信息综合分析；
4. 策略建议生成。

如果仅使用单一 LLM，一方面需要向模型一次性输入大量上下文，另一方面难以控制工具调用、任务依赖、失败重试和执行顺序。

因此，本项目将复杂任务拆分为：

```text
User Goal
    ↓
Supervisor Planning
    ↓
Dynamic Task DAG
    ↓
Specialist Agents
    ↓
Skill / Tool Runtime
    ↓
Analysis
    ↓
Report
```

## 3. System Architecture

整体架构如下：

```
┌──────────────────────────────────────────────┐
│                  User / API                  │
│                   FastAPI                    │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│               Supervisor Agent               │
│                                              │
│  Intent Classification                       │
│  Task Decomposition                          │
│  Agent Assignment                            │
│  Dependency DAG Planning                     │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│            Deterministic Scheduler            │
│                                              │
│  Dependency Resolution                       │
│  Async Concurrent Execution                  │
│  Timeout / Retry                             │
│  State Merge                                 │
│  Failure Propagation                         │
└─────────────┬──────────────┬─────────────────┘
              │              │
              ▼              ▼
      ┌──────────────┐ ┌──────────────┐
      │  Knowledge   │ │   Research   │
      │    Agent     │ │    Agent     │
      └──────┬───────┘ └──────┬───────┘
             │                │
             └────────┬───────┘
                      ▼
               ┌──────────────┐
               │   Analysis   │
               │    Agent     │
               └──────┬───────┘
                      │
                      ▼
               ┌──────────────┐
               │    Report    │
               │    Agent     │
               └──────────────┘

```

底层 Runtime：

```
Agent
  ↓
Skill Router
  ↓
Skill
  ↓
ToolCall
  ↓
Generic Tool Executor
  ↓
Tool Registry / MCP
```

## 4. Multi-Agent Design

当前系统主要包含以下 Agent。

### Supervisor Agent

负责复杂任务的认知层规划：

- 判断任务类型；
- 将复杂用户目标拆解为多个 Task；
- 为 Task 分配 Specialist Agent；
- 生成 `depends_on` 依赖关系；
- 构造动态 Task DAG。

Supervisor 不直接负责具体工具执行。

### Knowledge Agent

负责企业内部知识检索和证据化回答。

典型流程：

```
Knowledge Agent
      ↓
document_search Skill
      ↓
RAG Tool
      ↓
Evidence Context
      ↓
Grounded Answer
```

Knowledge Agent 要求：

- 只依据企业知识库证据回答；
- 不得虚构不存在的数据；
- 尽量保留 `[Source N]` 引用；
- 证据不足时明确说明。

### Research Agent

负责外部市场研究、竞争对手调研等任务。

典型流程：

```
Research Agent
      ↓
competitor_research Skill
      ↓
search Tool
      ↓
External Information
      ↓
Research Summary
```

当前 Search Tool 的架构和调用链已经接通。

> 当前版本中 Search Tool 仍可运行于 Mock 模式，因此涉及真实互联网数据的 Demo 需要在真实 Search Provider 接入后才能形成完整外部研究闭环。

### Analysis Agent

负责综合多个上游 Agent 的结果。

例如：

```
T1 Knowledge
      │
      ├───────┐
      │       │
T2 Research   │
      │       │
      └───┬───┘
          ↓
     T3 Analysis
```

Analysis Agent 会读取 dependency results，并完成：

- 多源信息综合；
- 机会识别；
- 风险分析；
- 策略建议；
- Evidence Boundary 控制。

------

### Report Agent

负责将 Specialist Agent 的最终业务结果整理为面向用户的答案。

为了降低重复上下文带来的 Token 消耗，Report Agent 支持：

```
Normal Report Path
```

和：

```
Synthesis Fast Path
```

当上游已经存在：

```
synthesis_analysis
```

时，Report 不再重新读取完整 Tool / RAG Runtime Data，而只基于 Analysis Agent 已完成的综合结果进行轻量整理。

## 5. Dynamic DAG Scheduler

项目没有完全依赖 LangGraph 来处理动态 Task DAG。

LangGraph 主要负责 workflow-level orchestration：

```
START
  ↓
Supervisor
  ↓
Scheduler
  ↓
Report
  ↓
END
```

而动态 Task DAG 由自研 Scheduler 执行。

Scheduler 负责：

- Dependency Resolution
- Ready Task Detection
- Async Concurrent Execution
- Retry
- Timeout
- Centralized State Merge
- Task Runtime Tracking
- Failure Handling

核心思想：

```
LLM decides WHAT should be done.

Scheduler decides WHEN and HOW it should run.
```

## 6. Concurrent Task Execution

对于不存在依赖关系的 Task，Scheduler 会并发执行。

例如：

```
             Supervisor
                 │
                 ▼
          ┌──────┴──────┐
          │             │
          ▼             ▼
     T1 Knowledge    T2 Research
          │             │
          └──────┬──────┘
                 ▼
             T3 Analysis
```

其中：

```
T1.depends_on = []
T2.depends_on = []

T3.depends_on = [T1, T2]
```

因此：

```
T1 || T2
```

可以通过 `asyncio.gather` 并发执行。

## 7. Agent → Skill → Tool Architecture

项目没有让 Agent 直接绑定具体工具，而是采用三级能力抽象：

```
Goal
 ↓
Agent
 ↓
Skill
 ↓
Tool
```

例如：

```
Research Agent
      ↓
competitor_research
      ↓
search
```

或者：

```
Knowledge Agent
      ↓
document_search
      ↓
RAG Tool
```

三层分别表示：

```
Agent = Business Role

Skill = Reusable Capability

Tool = Atomic Action
```

这样可以减少 Agent 与具体底层工具之间的耦合。

## 8. Hybrid RAG

Knowledge Agent 使用 Hybrid Retrieval Pipeline。

整体流程：

```
User Query
    ↓
Query Rewrite
    ↓
Dense Retrieval
    +
BM25 Retrieval
    ↓
Reciprocal Rank Fusion
    ↓
CrossEncoder Reranking
    ↓
Top Evidence
    ↓
Evidence Context
    ↓
Grounded Generation
```

主要组件包括：

- Query Rewrite
- Dense Embedding Retrieval
- BM25
- Reciprocal Rank Fusion
- CrossEncoder Reranker
- Evidence Context Construction
- Source Citation

企业知识库向量数据存储于 ChromaDB。

## 9. Memory System

项目将 Workflow State、RAG 和 Memory 明确分离。

### Workflow State

用于当前 Workflow 的临时执行状态。

### RAG

用于存储企业客观知识。

### Memory

用于保存跨 Session 有价值的历史信息和用户偏好。

Memory 体系包括：

```
Conversation Memory
Episodic Memory
Semantic Memory
```

Semantic Memory 支持：

- semantic retrieval；
- memory extraction；
- similarity matching；
- memory consolidation。

Consolidation 决策包括：

```
ADD
UPDATE
SKIP
DELETE
```

同时设计 Memory Fast Path，在明显没有长期记忆价值的消息上跳过 Memory LLM 调用，以减少额外 Token 消耗。

## 10. MCP Integration

项目支持 Model Context Protocol。

MCP Runtime 主要包括：

```
MCP Server
    ↓
Tool Discovery
    ↓
MCP Adapter
    ↓
Internal Tool Registry
    ↓
Generic Tool Executor
```

MCP 与 Agent 业务逻辑解耦，使外部能力可以动态接入现有 Tool Runtime。

## 11. Tool Governance

系统中的工具调用需要经过 Policy Engine。

Policy 包括：

```
ALLOW

REQUIRE_APPROVAL

DENY
```

执行链：

```
Agent
 ↓
Skill
 ↓
ToolCall
 ↓
Policy Engine
 ↓
Generic Executor
 ↓
Tool
```

Tool Executor 同时负责：

- Timeout
- Exception Handling
- Latency Tracking
- Policy Result Recording

------

## 12. Observability

项目实现了一套独立于 LangGraph 的 Structured Observability。

基于 `ContextVar` 为每个 Workflow 维护独立运行上下文，可以记录：

- workflow_id
- task_id
- agent
- skill
- tool
- LLM calls
- input tokens
- output tokens
- task latency
- tool latency
- workflow latency
- retry count
- memory calls
- estimated cost

典型 Trace：

```
workflow_started
        ↓
memory_fast_path
        ↓
supervisor_completed
        ↓
task_started
        ↓
tool_call
        ↓
llm_call
        ↓
task_completed
        ↓
scheduler_completed
        ↓
report_fast_path
        ↓
workflow_completed
```

同时预留 Langfuse Integration，用于：

- LangGraph Trace Visualization
- LLM Generation Tracking
- Session Tracking
- Prompt / Response Inspection
- Token Observation

## 13. Report Context Optimization

在早期版本中，Report Agent 会同时读取：

```
Full Tasks
+
Tool Results
+
RAG Chunks
+
Agent Results
```

导致大量重复上下文。

一次复杂 Workflow 中：

```
Report Input Tokens = 7007
Total Input Tokens  = 9717
```

随后引入：

```
Context Pruning
+
Synthesis Fast Path
```

优化后：

| Metric                | Before  | After   | Improvement |
| --------------------- | ------- | ------- | ----------- |
| Report Input Tokens   | 7007    | 1831    | ↓ 73.9%     |
| Workflow Input Tokens | 9717    | 4550    | ↓ 53.2%     |
| Total Tokens          | 13892   | 8527    | ↓ 38.6%     |
| Report Latency        | 8.61 s  | 7.20 s  | ↓ 16.3%     |
| Workflow Latency      | 32.92 s | 32.16 s | ↓ 2.3%      |

该优化说明：

> 对 Multi-Agent 系统而言，Agent 数量并不是唯一成本来源，跨 Agent Context Duplication 同样是重要的 Token Cost 来源。

------

## 14. Example Workflow

用户请求：

```
结合公司内部资料和外部市场信息，
分析 KnowledgeFlow 下一季度的发展机会，
并给出优先级建议。
```

Supervisor 动态规划：

```
T1
Knowledge Agent
收集内部 KnowledgeFlow 产品与战略资料

T2
Research Agent
调研外部市场与竞争信息

T3
Analysis Agent
depends_on = [T1, T2]

综合内部与外部信息并生成策略建议
```

Scheduler 执行：

```
T1 Knowledge ─────┐
                  ├──→ T3 Analysis ───→ Report
T2 Research ──────┘
```

其中 T1 和 T2 并发执行。

------

## 15. Regression Testing

项目提供固定 Demo Regression Suite，用于验证系统核心架构行为。

测试重点不是仅检查 HTTP 200，而是检查：

```
Agent Routing
Skill Routing
Tool Routing
DAG Dependency
Parallel Tasks
Trace Events
Retry
Token Regression
Memory Behavior
```

典型 Demo Case：

```
TC01 RAG Basic

TC02 Internal Knowledge

TC03 Research

TC04 Complex Multi-Agent DAG

TC05 Semantic Memory

TC06 Evidence-based Synthesis
```

Complex Workflow 还可以对输入 Token 设置上限，以避免未来修改导致 Context 膨胀重新出现。

## 16. Project Structure

```
enterprise-multi-agent/

├── app/
│   ├── agents/
│   │   ├── supervisor.py
│   │   ├── knowledge.py
│   │   ├── research.py
│   │   ├── analysis.py
│   │   └── report.py
│   │
│   ├── graph/
│   │   ├── graph.py
│   │   ├── scheduler.py
│   │   └── state.py
│   │
│   ├── skills/
│   │   ├── registry.py
│   │   └── router.py
│   │
│   ├── tools/
│   │   ├── registry.py
│   │   ├── executor.py
│   │   └── policy.py
│   │
│   ├── rag/
│   │   ├── retriever.py
│   │   ├── reranker.py
│   │   └── query_rewriter.py
│   │
│   ├── memory/
│   │   ├── manager.py
│   │   ├── extractor.py
│   │   ├── consolidator.py
│   │   └── router.py
│   │
│   ├── mcp/
│   │
│   ├── observability/
│   │   ├── context.py
│   │   ├── tracer.py
│   │   ├── llm_runtime.py
│   │   └── langfuse_integration.py
│   │
│   └── main.py
│
├── knowledge_base/
│
├── data/
│
├── tests/
│   ├── demo_cases.json
│   └── run_demo_regression.py
│
├── .env
└── README.md
```

## 17. Technology Stack

| Layer                  | Technology              |
| ---------------------- | ----------------------- |
| Backend                | FastAPI                 |
| Agent Workflow         | LangGraph               |
| LLM                    | DeepSeek                |
| Concurrency            | asyncio                 |
| Data Validation        | Pydantic                |
| Vector Database        | ChromaDB                |
| Dense Retrieval        | SentenceTransformers    |
| Sparse Retrieval       | BM25                    |
| Fusion                 | Reciprocal Rank Fusion  |
| Reranking              | CrossEncoder            |
| Memory Storage         | SQLite + ChromaDB       |
| External Tool Protocol | MCP                     |
| Observability          | Custom Structured Trace |
| LLM Observability      | Langfuse                |
| Testing                | Python + httpx          |

------

## 18. Quick Start

### Install

```
python -m venv .venv
```

Windows:

```
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```
pip install -r requirements.txt
```

------

### Environment

Create `.env`:

```
DEEPSEEK_API_KEY=your_api_key

LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=

LLM_INPUT_COST_PER_1M_USD=0
LLM_OUTPUT_COST_PER_1M_USD=0
```

Do not commit `.env`.

------

### Start API

```
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```
http://127.0.0.1:8000/docs
```

------

### Run Regression Suite

```
python tests/run_demo_regression.py
```

## 19. Core Design Decisions

### Why not let LLM directly control execution?

LLM is good at:

```
Understanding
Planning
Reasoning
```

but deterministic runtime should control:

```
Dependency
Concurrency
Retry
Timeout
State Merge
```

Therefore:

> LLM Planning + Deterministic Execution

------

### Why Agent → Skill → Tool?

To separate:

```
Business Role
Reusable Capability
Atomic Action
```

and reduce coupling between Agent logic and external tools.

------

### Why custom Scheduler if LangGraph already exists?

LangGraph is used for stable workflow-level orchestration.

The custom Scheduler is responsible for runtime Task DAGs dynamically generated by the Supervisor.

```
LangGraph
→ Static high-level workflow

Scheduler
→ Dynamic runtime task DAG
```

------

### Why separate RAG and Memory?

```
RAG
= Enterprise Knowledge

Memory
= Historical User / Task Context

State
= Current Workflow Runtime
```

These three types of context have different lifecycle and consistency requirements and should not be mixed together.

------

## 20. Current Limitations

Current version still has several areas that can be improved:

1. External Search may still run in Mock mode depending on configuration.
2. Cross-Agent citation preservation can be further improved.
3. Analysis Agent still needs stricter evidence-boundary control for unsupported external facts.
4. Tool Trace currently has room to improve Task / Agent attribution.
5. Langfuse integration can be extended with more custom spans.
6. Cost estimation requires actual model pricing configuration.

These limitations are intentionally kept visible instead of being hidden by generated content.
