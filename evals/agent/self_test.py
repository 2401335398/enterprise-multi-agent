"""
Agent Evaluation —— 断言引擎离线自测。

为什么需要它：断言引擎全部是 (expect, response) 上的纯函数，所以可以喂一份
**合成响应**进去，验证两件事——

  1. 一份形状正确的响应能让所有断言通过（不误报）；
  2. 把响应的某一处改坏，对应那条断言必须失败（不静默通过）。

第 2 条是关键：没有它，一个"永远返回 passed=True"的实现也能全绿。

不烧 token、不起服务，毫秒级。可直接 python 运行，也兼容 pytest。
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evals.agent.assertions import evaluate_expectation   # noqa: E402
from evals.agent.schema import Expectation                 # noqa: E402


# ============================================================
# 合成响应：一个"内外结合"的复杂工作流
# ============================================================

ANSWER = (
    "根据公司内部资料，KnowledgeFlow 3.2 于 2026 年 Q2 发布，新增了 "
    "Manufacturing Copilot 能力，面向制造业客户提供生产知识查询、设备文档检索"
    "与故障知识定位 [Source 1][Source 2]。结合外部市场调研，制造业知识管理"
    "需求正在持续上升 [Source 3]。综合来看，这与公司 2026 年扩大制造业客户"
    "覆盖的战略方向一致 [Source 4][Source 5]。"
)

COMPLEX_RESPONSE = {
    "session_id": "self-test",
    "answer": ANSWER,
    "task_type": "complex",
    "tasks": [
        {
            "id": "T1",
            "agent": "knowledge",
            "skill": "document_search",
            "depends_on": [],
            "status": "completed",
            "retry_count": 0,
            "started_at": 0.0,
            "completed_at": 3.0,
            "latency_ms": 3000,
            "tool_calls": [{"tool": "document_search", "arguments": {"query": "KnowledgeFlow 3.2"}}],
            "tool_results": [
                {
                    "tool": "document_search",
                    "result": {
                        "context": "[Source 1] ...\n[Source 5] ...",
                        "results": [
                            {"text": f"chunk {n}", "metadata": {"file_name": "product_update.txt"}}
                            for n in range(1, 6)
                        ],
                    },
                }
            ],
        },
        {
            "id": "T2",
            "agent": "research",
            "skill": "web_research",
            "depends_on": [],
            "status": "completed",
            "retry_count": 0,
            # 与 T1 区间重叠：0.1 < 3.0 且 0.0 < 4.0
            "started_at": 0.1,
            "completed_at": 4.0,
            "latency_ms": 3900,
            "tool_calls": [{"tool": "search", "arguments": {"query": "制造业 知识管理"}}],
            "tool_results": [
                {"tool": "search", "result": {"query": "制造业 知识管理", "results": ["mock"]}}
            ],
        },
        {
            "id": "T3",
            "agent": "analysis",
            "skill": "synthesis_analysis",
            "depends_on": ["T1", "T2"],
            "status": "completed",
            "retry_count": 0,
            # 在两个上游都完成之后才开始
            "started_at": 4.0,
            "completed_at": 6.0,
            "latency_ms": 2000,
            "tool_calls": [],
            "tool_results": [],
        },
    ],
    "trace": [
        "Supervisor Agent completed using planning",
        "Knowledge Agent completed using document_search",
        "Research Agent completed using web_research",
        "Report Agent completed using report_fast_path",
    ],
    "structured_trace": [
        {"event_type": "workflow_started"},
        {"event_type": "supervisor_completed"},
        {"event_type": "task_started", "metadata": {"task_id": "T1"}},
        {"event_type": "task_completed", "metadata": {"task_id": "T1"}},
        {"event_type": "scheduler_completed"},
        {"event_type": "workflow_completed"},
    ],
    "errors": [],
    "metrics": {
        "total_retries": 0,
        "total_llm_calls": 5,
        "total_input_tokens": 4200,
        "total_output_tokens": 900,
        "total_tool_calls": 2,
        "latency_ms": 6100.0,
        "estimated_cost_usd": 0.0031,
    },
}


MEMORY_RESPONSE = {
    "session_id": "self-test",
    "answer": "好的，我记下了。",
    "task_type": "simple",
    "tasks": [],
    "trace": [],
    "structured_trace": [
        {"event_type": "workflow_started"},
        {
            "event_type": "memory_semantic",
            "metadata": {"decision": {"action": "ADD", "memory_id": "m1"}},
        },
        {"event_type": "workflow_completed"},
    ],
    "errors": [],
    "metrics": {},
}


FAST_PATH_RESPONSE = {
    "session_id": "self-test",
    "answer": "好的。",
    "task_type": "simple",
    "tasks": [],
    "trace": [],
    "structured_trace": [
        {"event_type": "memory_fast_path"},
        {"event_type": "workflow_completed"},
    ],
    "errors": [],
    "metrics": {},
}


# ============================================================
# 覆盖全部断言 key 的 expect
# ============================================================

COMPLEX_EXPECT = Expectation(
    task_type_in=["complex"],
    required_agents=["knowledge", "research", "analysis"],
    required_skills=["document_search", "web_research", "synthesis_analysis"],
    required_tools=["document_search", "search"],
    forbidden_agents=["report"],
    forbidden_skills=["competitor_research"],
    forbidden_tools=["calculator"],
    min_task_count=3,
    max_task_count=4,
    require_dependency_task=True,
    require_parallel_root_tasks=True,
    require_all_tasks_completed=True,
    require_task_order=True,
    require_concurrency=True,
    required_events=["scheduler_completed"],
    required_events_any=["workflow_completed", "workflow_failed"],
    require_events_order=[
        "workflow_started",
        "supervisor_completed",
        "scheduler_completed",
        "workflow_completed",
    ],
    answer_contains_any=["Manufacturing Copilot"],
    answer_contains_none_of=["亿元"],
    min_answer_length=50,
    require_citation=True,
    min_citations=2,
    max_citation_index=True,
    require_trace_contains=["report_fast_path"],
    max_retries=0,
    max_llm_calls=8,
    max_input_tokens=7000,
    max_output_tokens=2000,
    max_tool_calls=4,
    max_latency_ms=60000,
    max_cost_usd=0.05,
    min_steps=2,
)

MEMORY_EXPECT = Expectation(
    require_memory_decision_in=["ADD"],
    require_memory_fast_path=False,
    min_steps=1,
)

FAST_PATH_EXPECT = Expectation(
    require_memory_fast_path=True,
    min_steps=1,
)


# ============================================================
# 变异：把响应改坏一处，对应断言必须失败
# ============================================================

def _set(path: tuple, value):
    def mutate(response: dict) -> None:
        node = response
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return mutate


MUTATIONS = [
    # key, 变异, 期望失败的断言
    ("task_type 改错",
     _set(("task_type",), "simple"), "task_type_in"),

    ("删掉 analysis 任务",
     lambda r: r["tasks"].pop(), "required_agents"),

    ("出现 report agent",
     lambda r: r["tasks"].append(
         {"id": "T4", "agent": "report", "skill": "synthesis_analysis",
          "depends_on": ["T3"], "status": "completed",
          "started_at": 6.0, "completed_at": 7.0}
     ), "forbidden_agents"),

    ("多出两个任务，越过 max_task_count",
     lambda r: r["tasks"].extend(
         {"id": f"T{n}", "agent": "analysis", "skill": "data_analysis",
          "depends_on": ["T3"], "status": "completed",
          "started_at": 6.0, "completed_at": 7.0}
         for n in (4, 5)
     ), "max_task_count"),

    ("清空全部 depends_on",
     lambda r: [t.update({"depends_on": []}) for t in r["tasks"]], "require_dependency_task"),

    ("T3 在上游完成前就开始（依赖名存实亡）",
     _set(("tasks", 2, "started_at"), 1.0), "require_task_order"),

    ("所有任务改成串行（并发消失）",
     lambda r: [
         t.update({"started_at": s, "completed_at": s + 1.0})
         for t, s in zip(r["tasks"], [0.0, 2.0, 4.0])
     ], "require_concurrency"),

    ("删掉 scheduler_completed 事件",
     lambda r: r["structured_trace"].pop(4), "require_events_order"),

    ("打乱事件顺序",
     lambda r: r["structured_trace"].reverse(), "require_events_order"),

    ("答案丢掉关键产品名",
     _set(("answer",), "根据资料，该版本新增了一些面向制造业的能力 [Source 1]。"), "answer_contains_any"),

    ("答案里出现编造的金额",
     _set(("answer",),
          ANSWER + " 该产品线营收约 3 亿元。"), "answer_contains_none_of"),

    ("答案缩到极短",
     _set(("answer",), "见资料。"), "min_answer_length"),

    ("答案去掉全部引用",
     _set(("answer",), ANSWER.replace("[Source 1]", "").replace("[Source 2]", "")
                         .replace("[Source 3]", "").replace("[Source 4]", "")
                         .replace("[Source 5]", "")), "require_citation"),

    ("引用编号越界（只有 5 条却引 [Source 9]）",
     _set(("answer",), ANSWER + " 另见 [Source 9]。"), "max_citation_index"),

    ("trace 里的 fast path 标记消失",
     lambda r: r.update({"trace": ["Supervisor Agent completed using planning"]}),
     "require_trace_contains"),

    ("重试次数超标",
     _set(("metrics", "total_retries"), 3), "max_retries"),

    ("输入 token 突破天花板",
     _set(("metrics", "total_input_tokens"), 99999), "max_input_tokens"),

    ("延迟突破天花板",
     _set(("metrics", "latency_ms"), 120000.0), "max_latency_ms"),

    ("出现预期外 error",
     _set(("errors",), ["Task T1 failed: boom"]), "no_unexpected_errors"),

    ("中途中断，只跑了 1 步",
     None, "min_steps"),
]


# ============================================================
# 运行
# ============================================================

def _keys(checks) -> set[str]:
    return {check.key for check in checks}


def run_self_test() -> int:
    failures: list[str] = []

    # ---------- 1. 正向：合成长响应必须全绿 ----------

    checks = evaluate_expectation(
        expect=COMPLEX_EXPECT,
        response=COMPLEX_RESPONSE,
        steps_executed=2,
    )

    bad = [c for c in checks if not c.passed]

    if bad:
        failures.append(
            "复杂响应应全部通过，实际失败: "
            + json.dumps(
                [{"key": c.key, "expected": c.expected, "actual": c.actual,
                  "detail": c.detail} for c in bad],
                ensure_ascii=False,
            )
        )

    # 声明的每个 key 都必须真的被求值过，避免"写了但引擎不读"
    declared = {
        key for key, value in COMPLEX_EXPECT.model_dump().items()
        if value not in (None, [], False)
    }
    # require_* 布尔为 False 时不产生 check，这里全为 True，不冲突
    unevaluated = declared - _keys(checks)

    if unevaluated:
        failures.append(f"这些 expect 字段没有被引擎读取: {sorted(unevaluated)}")

    print(f"[正向] 复杂响应: {len(checks)} 条断言，{len(bad)} 条失败")

    # ---------- 2. 正向：记忆响应的两类决策 ----------

    for label, expect, response, expected_key in (
        ("记忆 ADD", MEMORY_EXPECT, MEMORY_RESPONSE, "require_memory_decision_in"),
        ("记忆快路径", FAST_PATH_EXPECT, FAST_PATH_RESPONSE, "require_memory_fast_path"),
    ):
        result = evaluate_expectation(
            expect=expect, response=response, steps_executed=1
        )
        bad = [c for c in result if not c.passed]

        if bad:
            failures.append(f"{label} 应通过，实际失败: {[c.key for c in bad]}")

        if expected_key not in _keys(result):
            failures.append(f"{label} 未产生 {expected_key}")

        print(f"[正向] {label}: {len(result)} 条断言，{len(bad)} 条失败")

    # 记忆决策反向：ADD 不允许出现在只接受 SKIP 的期望里
    result = evaluate_expectation(
        expect=Expectation(require_memory_decision_in=["SKIP"]),
        response=MEMORY_RESPONSE,
        steps_executed=1,
    )
    if all(c.passed for c in result):
        failures.append("记忆决策断言失效：ADD 竟然满足了 require_memory_decision_in=['SKIP']")

    # ---------- 3. 反向：逐项变异必须被抓住 ----------

    caught = 0

    for name, mutate, expected_key in MUTATIONS:
        response = copy.deepcopy(COMPLEX_RESPONSE)

        if mutate is not None:
            mutate(response)

        steps = 1 if expected_key == "min_steps" else 2

        result = evaluate_expectation(
            expect=COMPLEX_EXPECT,
            response=response,
            steps_executed=steps,
        )

        failed_keys = {c.key for c in result if not c.passed}

        if expected_key not in failed_keys:
            failures.append(
                f"变异『{name}』未被抓住：期望 {expected_key} 失败，"
                f"实际失败集为 {sorted(failed_keys) or '空'}"
            )
        else:
            caught += 1

    print(f"[反向] 变异用例: {caught}/{len(MUTATIONS)} 被正确抓住")

    # ---------- 汇总 ----------

    print()

    if failures:
        print(f"SELF-TEST FAILED ({len(failures)} 项)")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("SELF-TEST PASSED —— 断言引擎既不误报，也不静默放过")
    return 0


# ============================================================
# pytest 入口
# ============================================================

def test_assertion_engine() -> None:
    assert run_self_test() == 0


if __name__ == "__main__":
    sys.exit(run_self_test())
