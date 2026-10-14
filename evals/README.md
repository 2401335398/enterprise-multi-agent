# Evaluation

两条互相独立、粒度不同的评测线：

| 目录 | 测什么 | 需要 LLM | 需要服务 | 耗时 |
|---|---|---|---|---|
| [rag/](rag/) | 检索层本身（Hit@1/3/5 + MRR） | 否 | 否 | 秒级 |
| [agent/](agent/) | 端到端全链路 + 离线专项 | e2e 需要 | e2e 需要 | 见下 |

`tests/run_demo_regression.py` 是第三条线（6 条冒烟回归），保留不动。

---

## rag/ —— 检索层基线

纯离线，不起服务，不调 LLM，直接跑容器内的检索器：

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evals/rag/evaluate_retrieval.py
```

数据集：[rag/datasets/retrieval_cases.json](rag/datasets/retrieval_cases.json)，8 条 NIST AI RMF 英文问题。
产出 vector / hybrid / hybrid_rerank 三档指标对比。

> **前置条件**：Chroma 索引必须已构建。若 `data/chroma/` 不存在或为空，所有指标都是 0。

---

## agent/ —— 端到端 Agent 评测

### 快速开始

```bash
# 1. 离线专项（秒级，无 LLM，无需服务，可进 CI）
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evals/agent/run_agent_eval.py --scope component

# 2. 断言引擎自测（毫秒级，验证引擎本身没坏）
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evals/agent/self_test.py

# 3. 端到端前必须先起服务
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. 端到端全量
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evals/agent/run_agent_eval.py --scope all
```

### 常用参数

```bash
--scope {e2e,component,all}      跑哪一层（默认 all）
--only DIMENSION|TAG|ID          只跑匹配的案例，可重复
                                 （如 --only dag_runtime --only smoke）
--repeat N                       每条重复 N 次，用于复现抖动
--no-judge                       跳过 LLM-as-Judge（快、零 judge 成本）
--judge-strict                   把 judge 低分计入失败（默认不计入）
--show-all-checks                打印每条断言的实际值，而不仅是失败项
--cleanup-memory                 跑完清理本次 run 的记忆记录
--skip-preflight                 跳过启动前的连通性检查
--base-url / --out               服务地址 / 结果输出目录
```

退出码：确定性断言全过 → `0`，否则 `1`。judge 默认不影响退出码。

### 结果产物

每次运行写一份 `agent/results/agent_eval_<时间戳>.json`（已 gitignore），包含：

- `run` —— 时间戳、git commit、数据集 SHA256、被测模型、judge 模型与 prompt 版本
- `cases[]` —— 每条案例的逐步断言（key / expected / actual / passed / detail）、
  judge 分项与理由、`observed` 观测快照（任务序列、skill、工具、事件、metrics）
- `summary` —— 分维度通过率、judge 均分、token、成本、p50/p95 延迟、失败清单

**可离线复跑**：断言引擎是 `(expect, response)` 上的纯函数，所以历史 JSON 可以
重新判定而不烧 token。

---

## 评测集结构

[agent/datasets/agent_cases.json](agent/datasets/agent_cases.json) —— 40 条端到端案例：

| 维度 | 条数 | 覆盖目标 |
|---|---|---|
| `planning` | 7 | 任务类型分类、**不过度拆分**、knowledge/research 分流 |
| `knowledge_grounding` | 6 | 引用保留、**该拒答时拒答 / 不该拒答时别乱拒**、PDF 多跳、跨文档 |
| `research_external` | 4 | 竞品关键词路由、browser 触发、**必须声明数据是 Mock** |
| `dag_runtime` | 5 | 并行、链式依赖、**依赖顺序真的被遵守**、事件顺序 |
| `analysis_synthesis` | 4 | synthesis vs data 切换、空依赖不该 synthesis |
| `memory` | 6 | fast path、ADD / UPDATE / SKIP / DELETE、当前请求压过历史 |
| `robustness` | 5 | 超长输入、提示词注入、自相矛盾、域外问题、极短输入 |
| `report_budget` | 3 | fast path 命中、Token 天花板、延迟天花板 |

外加 [agent/component_checks.py](agent/component_checks.py) 里 5 条离线专项
（工具治理 / Skill 路由 / 检索基线 / 过滤器缺陷 / 引用编号地基）。

### 案例里几个不直观的约定

- **`session_mode: "shared"`** —— 多轮案例必须在同一 session 内。记忆是 session
  作用域的（`semantic_memory_store.search()` 强制 `where={"session_id": ...}`），
  不存在跨 session 复用。
- **步级 `expect` 优先** —— 最后一步若写了步级 expect，则案例级 expect 不生效。
  记忆案例因此把 `min_steps` 也写进步级 expect。
- **`extra="forbid"`** —— 断言字段写错名字会在**加载时**报错，而不是被静默忽略。
  （老 runner 的 `min_steps` 就是这样被吞掉的。）

---

## 需要知道的既有约束

这些不是评测的缺陷，是系统的现状，直接决定了案例能断言什么：

1. **`search` / `browser` 是 Mock**，返回硬编码文案。研究类案例只能验路由、
   不编造、以及**是否诚实声明数据是模拟的**。
2. **工具治理无法端到端评测**。Agent 能触达的工具全是 ALLOW，所有策略的
   `allowed_agents` 都为空 → 不存在任何会被拒的 agent→tool 组合。只在离线专项验证。
3. **知识库拒答不是自动的**。Chroma 永远返回 top-5，context 不会为空，所以
   `knowledge.py` 的"证据不足"硬编码分支不会触发——拒答完全靠 LLM 遵守 prompt。
   这是**有真实失败风险的优质案例**，也是首个应当关注的基线项。
4. **BM25 收下 `filters` 但从不使用**。`document_search` 目前不传 filters，
   所以这个缺陷还没被端到端路径触发；一旦开始传，就是静默的召回污染。
   离线专项 `CMP-RAG-02` 把这个现状固化了。
5. **`data_analysis` / `synthesis_analysis` 不产生 tool_calls**，analysis 任务的
   `required_tools` 必须为空。

---

## 基线

### 离线（已标定，可复现）

`--scope component` 全绿：5/5，退出码 0。

检索质量（8 条 NIST 案例，51 文档 / 153 chunk）：

| 策略 | Hit@1 | Hit@3 | Hit@5 | MRR |
|---|---|---|---|---|
| vector | 0.667 | 1.000 | 1.000 | 0.778 |
| hybrid | 0.667 | 1.000 | 1.000 | 0.833 |
| hybrid_rerank | 0.667 | 1.000 | 1.000 | 0.833 |

> hybrid_rerank 与 hybrid 完全一致 —— 在这 8 条集合上 reranker 没有改变任何一条
> 的排序。样本量太小，不足以判定 reranker 无效，但值得记住。

`self_test.py`：20/20 变异用例被正确抓住，33 条断言在合成长响应上全部通过。

### 端到端（第一轮，2026-10-08）

单轮 40 条，`deepseek-chat`，`git 8794f82`，耗时 544s（9.1 分钟），219,501 token。

| 维度 | 通过 | 总数 | 通过率 |
|---|---|---|---|
| memory | 4 | 6 | 66.7% |
| planning | 6 | 7 | 85.7% |
| robustness | 5 | 5 | 100% |
| knowledge_grounding | 6 | 6 | 100% |
| research_external | 4 | 4 | 100% |
| dag_runtime | 5 | 5 | 100% |
| analysis_synthesis | 4 | 4 | 100% |
| report_budget | 3 | 3 | 100% |
| **合计** | **42** | **45** | **93.3%** |

延迟 p50 12.1s / p95 28.4s。judge 均分：groundedness 5.0、evidence_boundary 5.0、
citation 4.8、completeness 4.5、synthesis_quality 4.0，无一次 `fabricated_facts`。

> 原始运行记录是 `agent_eval_20261008_150140.json`（41/45）。其中 `EV-ROB-04`
> 经查是**评测自身的断言写错**（见下），修正后单独复跑该条通过，故基线记 42/45。
> 该文件对应修正前的数据集 SHA；修正后的 SHA 为 `8347f9fc…`。

**尚未标定抖动。** 单轮不足以判定 flaky，第二轮对比留待下次。以下三条是首轮
发现的**真实问题**，不是评测缺陷，保留断言不动：

| 案例 | 现象 | 判断 |
|---|---|---|
| `EV-PLN-05` | 一个完全落在知识库内的问题被拆成 4 个任务，多出一个不必要的 research | 过度拆分。答案本身质量不错，但规划层多花了两次 LLM 调用 |
| `EV-MEM-03` | 近似同义改口（中文→英文）得到 `ADD` 而非 `UPDATE` | 合并相似度未越过 0.72 阈值，退化为无 LLM 的 ADD。正是计划里预判的风险 |
| `EV-MEM-05` | 显式取消语言偏好得到 `ADD` 而非 `DELETE` | **最值得关注**：用户可见行为是对的（答案确实说"已取消"），但记忆库里旧偏好仍在，只是**新增了一条"已取消"的记忆**。下一轮两条互相矛盾的记忆会一起被检索出来 |

### 关于成本数字

结果 JSON 里的 `estimated_cost_usd` **默认为 0**，因为
[app/observability/cost.py](../../app/observability/cost.py) 从环境变量读单价，
没有内置任何模型的价格。要让成本可见，需自行设置：

```bash
LLM_INPUT_COST_PER_1M_USD=<你的输入单价>
LLM_OUTPUT_COST_PER_1M_USD=<你的输出单价>
```

在那之前，`0.0 USD` 应读作"未配置"，而不是"免费"。

### 标定流程（下次照做）

1. 跑满一轮 `--scope e2e`，记录分维度通过率。
2. 再跑一轮，对比两份 JSON。**两轮结果不一致的案例标记为 flaky**，
   放宽断言或改用 `--repeat` 观察，否则评测集会退化成随机报警器。
3. 把确认后的基线更新到本节。
4. 确认为模型能力边界而非回归的案例，在它的 `expected_behavior` 里注明，
   **不要删断言**。

### 一条断言设计教训

`answer_contains_none_of` 只能放**在正确答案里不可能出现的字符串**。

首轮 `EV-ROB-04`（域外天气问题）原本block了 `["晴","多云","摄氏度","℃","空气质量"]`，
结果误杀了满分答案——正确的拒答恰恰会列出"我无法提供温度、风力、空气质量等信息"。
按主题名词做黑名单，无法区分"编造了一个值"和"列举自己拒绝回答的类别"。

改成只要求出现明确的无法回答声明，把"是否编造"交给 judge 的 `groundedness`。

同理，`EV-KNW-02` 的 `["亿元","万元"]` 是单位而非主题词，风险低得多，暂时保留。

---

## 添加案例

1. 在 `datasets/agent_cases.json` 里加一条，`dimension` 用现有 8 个之一。
2. **期望值必须来自真实语料**（`data/knowledge_base/`）。先确认答案确实
   在库内还是不在，再决定是断言"答对"还是断言"拒答"。
3. 改动断言引擎时，同步更新 [agent/self_test.py](agent/self_test.py) ——
   新增 key 必须在 `COMPLEX_EXPECT` 里被覆盖，否则自测会报"字段没有被引擎读取"。
4. 跑 `--only <你的 dimension>` 验证过滤生效。

---

## 已知待办

- [x] 端到端首轮标定（42/45，见上）
- [ ] 第二轮回跑，确认抖动 / 标记 flaky
- [ ] `EV-MEM-05`：确认"取消偏好"是否应该真正删除旧记忆（目前是新增一条反向记忆）
- [ ] 配置 `LLM_*_COST_PER_1M_USD`，让成本数字可用
- [ ] `tests/run_demo_regression.py` 与新的断言引擎存在两套实现，可考虑合并
- [ ] `evals/rag` 有两套互不相通的检索数据集，可考虑合并
