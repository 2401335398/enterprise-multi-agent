"""
Agent Evaluation —— 数据模型。

两类模型：

1. 案例模型（EvalCase 及下属），用 pydantic 校验数据集文件。
   全部 expect 字段都设了 extra="forbid"，因此数据集里写错一个断言 key
   会在加载阶段直接报错，而不是被静默忽略。
   （历史遗留教训：tests/demo_cases.json 的 TC05 写了 min_steps，
   但 run_demo_regression.py 从未读取，该期望被静默吞掉。）

2. 结果模型，用 dataclass，便于 asdict() 直接落 JSON。

注：pydantic v2 对可变默认值会按实例深拷贝，因此列表默认值直接写 []。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


# ============================================================
# 案例模型
# ============================================================

class Expectation(BaseModel):
    """
    单次 /api/chat 响应的确定性断言集合。

    所有字段默认为 None / 空列表，表示"不做该断言"。
    """

    model_config = ConfigDict(extra="forbid")

    # ---------- 路由 ----------
    task_type_in: list[str] | None = None
    required_agents: list[str] = []
    required_skills: list[str] = []
    required_tools: list[str] = []
    forbidden_agents: list[str] = []
    forbidden_skills: list[str] = []
    forbidden_tools: list[str] = []

    # ---------- DAG 形状 ----------
    min_task_count: int | None = None
    max_task_count: int | None = None
    require_dependency_task: bool = False
    require_parallel_root_tasks: bool = False
    require_all_tasks_completed: bool = False

    # ---------- 时序（读 task 的 started_at / completed_at）----------
    # 依赖是真的被遵守，而不只是 depends_on 字段非空
    require_task_order: bool = False
    # 并发是真的发生，而不只是存在两个根任务
    require_concurrency: bool = False

    # ---------- 事件 ----------
    required_events: list[str] = []
    required_events_any: list[str] = []
    # 有序子序列
    require_events_order: list[str] = []

    # ---------- 答案文本 ----------
    answer_contains_any: list[str] = []
    answer_contains_none_of: list[str] = []
    min_answer_length: int | None = None

    # ---------- 引用 ----------
    require_citation: bool | None = None
    min_citations: int | None = None
    # [Source N] 里的 N 不得超过实际检索条数
    max_citation_index: bool = False

    # ---------- 原始 trace 文案（ChatResponse.trace）----------
    require_trace_contains: list[str] = []

    # ---------- 预算 ----------
    max_retries: int | None = None
    max_llm_calls: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    max_latency_ms: float | None = None
    max_cost_usd: float | None = None

    # ---------- 记忆 ----------
    # 读 memory_semantic 事件的 metadata.decision.action
    require_memory_decision_in: list[str] = []
    require_memory_fast_path: bool | None = None

    # ---------- 错误处理 ----------
    # 默认任何 errors 非空即失败；下列出预期内的 error 子串可豁免
    allow_errors_containing: list[str] = []

    # ---------- 执行完整性 ----------
    # 断言本次运行真的跑满了 N 步（中途抛错会 break，导致步数不足）
    min_steps: int | None = None


class JudgeConfig(BaseModel):
    """LLM-as-Judge 的按案例配置。"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    dimensions: list[str] = []
    # 取证来源，形如 "task_with_skill:document_search"
    evidence_from: str | None = None


class Step(BaseModel):
    """一次 /api/chat 调用。"""

    model_config = ConfigDict(extra="forbid")

    message: str
    # 该步单独的断言；用于多轮记忆案例的中间轮
    expect: Expectation | None = None


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    dimension: str
    description: str = ""
    tags: list[str] = []

    # fresh：不传 session_id，由服务端生成（每步独立 session）
    # shared：整案共用一个 session_id，用于多轮记忆
    session_mode: Literal["fresh", "shared"] = "fresh"

    steps: list[Step]
    # 对最后一步响应生效
    expect: Expectation | None = None
    judge: JudgeConfig | None = None

    # 已知会失败 / 抖动的说明，仅作人读注释，不参与判定
    expected_behavior: str = ""


class EvalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    description: str = ""
    cases: list[EvalCase]


# ============================================================
# 结果模型
# ============================================================

@dataclass
class CheckResult:
    """一条断言的判定结果。"""

    key: str
    passed: bool
    expected: Any = None
    actual: Any = None
    detail: str = ""


@dataclass
class StepResult:
    step: int
    message: str
    failed: bool
    checks: list[CheckResult] = field(default_factory=list)
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class CaseResult:
    id: str
    name: str
    dimension: str
    tags: list[str] = field(default_factory=list)
    kind: str = "e2e"                       # e2e | component
    elapsed_ms: float = 0.0
    passed: bool = False
    steps: list[StepResult] = field(default_factory=list)
    failed_keys: list[str] = field(default_factory=list)
    judge: dict[str, Any] | None = None
    observed: dict[str, Any] = field(default_factory=dict)
    answer_excerpt: str = ""
    error: str | None = None


@dataclass
class RunResult:
    run: dict[str, Any] = field(default_factory=dict)
    cases: list[CaseResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
