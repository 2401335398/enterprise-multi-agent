# 上下文工程变更日志

## 2026-10-13：最小上下文策略接入

### 背景

系统能够将 Conversation、Semantic 和 Episodic Memory 写入存储，Supervisor
也能读取 `memory_context`，但 Specialist Agent 和 Report Agent 无法看到经过筛选的
历史上下文。因此，“我刚刚问了什么”会被错误路由到 Knowledge Agent，并尝试从
企业知识库回答。

### 设计目标

- 不替换现有 Memory、LangGraph、Scheduler、Agent 或 RAG 架构。
- 明确区分历史查询、上下文跟进和独立请求。
- 只给确实依赖历史的任务向 Specialist/Report 注入上下文，避免全量广播带来的 Token 膨胀。
- 历史消息只用于理解指代，不能替代 RAG/Tool Evidence。
- 对“上一条问了什么”采用确定性读取，不调用 LLM 或 RAG。

### 行为变化

| 请求类型 | 新行为 |
|---|---|
| `我刚刚问了什么` | 从当前 Session 的 Conversation Memory 返回最近一条用户消息 |
| `你刚才回复了什么` | 返回最近一条 Assistant 消息 |
| `继续分析刚才的方案` | 原工作流不变，但下游 Agent 获得经过裁剪的历史上下文 |
| 独立知识或研究请求 | 原工作流不变，不向 Specialist/Report 广播新增的历史上下文 |

### 文件变更

| 文件 | 变更 |
|---|---|
| `app/context_engineering.py` | 新增确定性意图识别、历史直答、上下文裁剪和统一结果结构 |
| `app/api/chat.py` | 在写入当前消息前选择上下文；接入历史直答；记录上下文 Trace |
| `app/graph/state.py` | 新增 `context_intent` 与 `agent_context` |
| `app/agents/knowledge.py` | 按需接收历史上下文，明确其不能替代 RAG Evidence |
| `app/agents/research.py` | 按需接收历史上下文，明确其不能作为外部研究证据 |
| `app/agents/analysis.py` | 按需接收历史上下文并保持当前请求优先 |
| `app/agents/report.py` | 按需接收历史上下文，用于指代和格式延续 |
| `tests/security/test_context_engineering.py` | 新增策略、直答绕过 Workflow、状态传播测试 |

### 可观测性

每次请求新增 `context_selected` Trace，只记录：

- `intent`
- 选择原因
- 是否走确定性直答
- 注入上下文的字符数

直答请求额外记录 `context_direct_answer`。Trace 不保存历史正文，避免扩大敏感数据暴露面。

### 边界和风险

- 意图识别采用保守的正则规则，不调用模型；没有明确历史信号的请求仍按独立请求处理。
- 注入内容上限为 6000 字符，超出时保留首尾并标记截断。
- 当前只确定性处理最近一条用户问题或 Assistant 回复，不负责生成长对话摘要。
- Supervisor 继续使用原有的 `memory_context` 完成任务规划；本次选择策略控制的是新增给 Specialist/Report 的 `agent_context`，以降低改动范围和规划回归风险。
- 多实例部署仍依赖现有 Memory 后端的一致性，本次没有改变存储架构。

### 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests\security\test_context_engineering.py -v -p no:cacheprovider --basetemp .test-tmp\context
.\.venv\Scripts\python.exe -m pytest tests\security -v -p no:cacheprovider --basetemp .test-tmp\security
.\.venv\Scripts\python.exe -m pytest tests\rag -v -p no:cacheprovider --basetemp .test-tmp\rag
```

### 本次验证结果

- 上下文工程专项测试：`6 passed`
- 完整安全测试：`95 passed`
- RAG 回归测试：`5 passed`
- 验证日期：`2026-10-13`

### 回滚方法

需要回滚本次上下文工程时：

1. 删除 `app/context_engineering.py` 和对应测试。
2. 从 `app/api/chat.py` 移除 `build_context_decision`、`build_direct_workflow_result`、
   `context_selected`、`context_direct_answer` 以及直答分支。
3. 从 `AgentState` 移除 `context_intent` 和 `agent_context`。
4. 从四个 Agent Prompt 移除 `agent_context` 段落。

Memory 数据格式、SQLite 表结构、API 请求结构和 API 响应 Schema 均未改变，回滚不需要迁移数据。

## 2026-10-13：跟进延迟与前端会话持久化优化

### 背景

- “继续分析刚才的方案”仍会被 Supervisor 重新拆成完整的 Knowledge、Research、Analysis 流程，实测一次请求产生 6 次 LLM 调用并耗时约 76.5 秒。
- 后端历史仍在 `data/memory.db`，但前端依赖浏览器保存后端返回的 Session ID；首次响应未持久化或详细 Trace 超出 `localStorage` 容量时，会话关联可能丢失。

### 行为变化

- 明确的继续分析请求在已有 `agent_context` 且没有新检索要求时，跳过 Supervisor LLM，确定性创建一个 Analysis 任务，再由 Report 汇总；正常情况下由约 6 次 LLM 降为 2 次。
- 包含“重新检索、最新资料、知识库、外部资料”等新证据要求时，继续使用原 Supervisor 和完整工作流。
- 前端第一次请求使用本地会话 UUID 作为后端 Session 基础，不再依赖首次响应才能建立稳定映射。
- 浏览器存储超限时依次尝试减少会话数量、移除详细 Response/Trace；优先保留会话 ID 和可见消息正文。

### 文件变更

| 文件 | 变更 |
|---|---|
| `app/agents/supervisor.py` | 新增保守的上下文跟进快速规划策略 |
| `frontend/src/App.tsx` | 首次请求发送稳定的本地会话 ID |
| `frontend/src/storage.ts` | 新增 Session ID 解析和存储超限降级 |
| `frontend/src/storage.test.ts` | 新增稳定 Session 与精简存储测试 |
| `tests/security/test_context_engineering.py` | 新增快速规划边界和跳过 Supervisor LLM 测试 |

### 边界

- 快速路径只处理明确以“继续、接着、进一步、基于上文”等形式表达的延续请求。
- 快速路径复用现有上下文，不执行新的知识检索或外部研究；明确要求新证据时不会命中。
- 旧会话数据没有被删除，但本次不新增后端会话列表 API，因此已经丢失 Session ID 的浏览器仍不能自动枚举历史会话。
- 降级保存时会保留聊天正文和 Session ID，但刷新页面后不再展示被移除的旧运行详情和 Trace。

### 本次验证结果

- 上下文工程专项测试：`10 passed`
- 完整安全测试：`99 passed`
- 前端测试：`11 passed`
- 前端 lint：通过
- 前端生产构建：通过

### 回滚方法

1. 从 `app/agents/supervisor.py` 移除 `build_contextual_follow_up_plan` 和对应分支。
2. 将 `App.tsx` 的 Session 参数恢复为 `activeSession.backendSessionId`。
3. 从 `storage.ts` 移除 `requestSessionId`，并恢复原 `saveSessions` 实现。
4. 删除本节列出的新增测试。
