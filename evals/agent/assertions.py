"""
Agent Evaluation —— 确定性断言引擎。

设计原则：`evaluate_expectation()` 是纯函数，只依赖 (expect, response, steps_executed)。
因此：

- 可以对任意历史结果 JSON 离线复跑断言，不烧 token；
- 可以单独做单元测试；
- 不存在"评测器需要调 LLM 才能判断结构"的情况。

响应形状来自 app/api/chat.py 的 ChatResponse：
    {session_id, answer, task_type, tasks, trace, structured_trace, errors, metrics}
"""

from __future__ import annotations

import re
from typing import Any

from evals.agent.schema import CheckResult, Expectation

# perf_counter 时间戳比较的容差（秒）
TIME_TOLERANCE = 0.001

CITATION_PATTERN = re.compile(r"\[Source\s*(\d+)\]", re.IGNORECASE)


# ============================================================
# 观测辅助
# ============================================================

def collect_events(response: dict) -> list[str]:
    """按顺序取 structured_trace 里的 event_type。"""

    return [
        str(event.get("event_type"))
        for event in (response.get("structured_trace") or [])
        if isinstance(event, dict)
    ]


def collect_agents(response: dict) -> list[str]:
    return [
        str(task.get("agent"))
        for task in (response.get("tasks") or [])
        if task.get("agent")
    ]


def collect_skills(response: dict) -> list[str]:
    return [
        str(task.get("skill"))
        for task in (response.get("tasks") or [])
        if task.get("skill")
    ]


def collect_tools(response: dict) -> list[str]:
    """
    汇总 task 上的 tool_calls 与 tool_results 里的工具名。

    两者取并集：被 Policy 拒绝的调用仍会出现在 tool_calls 里，
    因此并集等价于"这次运行尝试调用了哪些工具"。
    """

    names: set[str] = set()

    for task in (response.get("tasks") or []):
        for call in (task.get("tool_calls") or []):
            if isinstance(call, dict) and call.get("tool"):
                names.add(str(call["tool"]))

        for result in (task.get("tool_results") or []):
            if isinstance(result, dict) and result.get("tool"):
                names.add(str(result["tool"]))

    return sorted(names)


def count_citations(answer: str) -> list[int]:
    """取出答案里所有 [Source N] 的 N。"""

    return [
        int(match)
        for match in CITATION_PATTERN.findall(answer or "")
    ]


def retrieved_source_count(response: dict) -> int | None:
    """
    本次运行实际检索到多少条证据。

    路径：task.tool_results[*].result.results
          （document_search 工具返回的 RAGService.search 输出）
    找不到时返回 None，调用方据此降级而不是误判。
    """

    for task in (response.get("tasks") or []):
        for result in (task.get("tool_results") or []):
            if not isinstance(result, dict):
                continue
            if result.get("tool") != "document_search":
                continue

            payload = result.get("result")
            if not isinstance(payload, dict):
                continue

            results = payload.get("results")
            if isinstance(results, list):
                return len(results)

    return None


def task_intervals(response: dict) -> dict[str, tuple[float, float]]:
    """task_id -> (started_at, completed_at)，只保留两者都存在的任务。"""

    intervals: dict[str, tuple[float, float]] = {}

    for task in (response.get("tasks") or []):
        started = task.get("started_at")
        completed = task.get("completed_at")

        if started is None or completed is None:
            continue

        intervals[str(task.get("id"))] = (float(started), float(completed))

    return intervals


def _intervals_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def memory_decision(response: dict) -> str | None:
    """最后一次 memory_semantic 事件里的 consolidation action。"""

    decision = None

    for event in (response.get("structured_trace") or []):
        if not isinstance(event, dict):
            continue
        if event.get("event_type") != "memory_semantic":
            continue

        payload = (event.get("metadata") or {}).get("decision")
        if isinstance(payload, dict):
            decision = payload.get("action")

    return str(decision).upper() if decision else None


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    """needle 是否为 haystack 的有序子序列。"""

    index = 0

    for item in haystack:
        if index < len(needle) and item == needle[index]:
            index += 1

    return index == len(needle)


def summarize_observation(response: dict) -> dict[str, Any]:
    """写进结果的紧凑观测快照，用于人工定位失败原因。"""

    tasks = response.get("tasks") or []

    return {
        "task_type": response.get("task_type"),
        "task_sequence": [
            {
                "id": task.get("id"),
                "agent": task.get("agent"),
                "skill": task.get("skill"),
                "depends_on": task.get("depends_on"),
                "status": task.get("status"),
                "retry_count": task.get("retry_count"),
                "latency_ms": task.get("latency_ms"),
            }
            for task in tasks
        ],
        "agents": collect_agents(response),
        "skills": collect_skills(response),
        "tools": collect_tools(response),
        "event_types": collect_events(response),
        "metrics": response.get("metrics") or {},
        "errors": list(response.get("errors") or []),
    }


# ============================================================
# 断言实现
# ============================================================

def _check_subset(key: str, required: list[str], actual: list[str]) -> CheckResult:
    missing = sorted(set(required) - set(actual))

    return CheckResult(
        key=key,
        passed=not missing,
        expected=required,
        actual=actual,
        detail="" if not missing else f"缺失: {missing}",
    )


def _check_forbidden(key: str, forbidden: list[str], actual: list[str]) -> CheckResult:
    present = sorted(set(forbidden) & set(actual))

    return CheckResult(
        key=key,
        passed=not present,
        expected=f"不得出现 {forbidden}",
        actual=actual,
        detail="" if not present else f"不该出现却出现了: {present}",
    )


def _check_limit(key: str, limit: float, actual: float) -> CheckResult:
    return CheckResult(
        key=key,
        passed=actual <= limit,
        expected=f"<= {limit}",
        actual=actual,
        detail="" if actual <= limit else f"超出上限 {actual} > {limit}",
    )


def _check_no_errors(expect: Expectation, response: dict) -> CheckResult:
    """
    默认：errors 非空即失败。
    若声明了 allow_errors_containing，则命中这些子串的 error 被豁免，
    剩下的仍会导致失败。
    """

    errors = [str(e) for e in (response.get("errors") or [])]

    allowed = expect.allow_errors_containing

    if allowed:
        unexpected = [
            error
            for error in errors
            if not any(token in error for token in allowed)
        ]
    else:
        unexpected = errors

    return CheckResult(
        key="no_unexpected_errors",
        passed=not unexpected,
        expected=f"无预期外 error（豁免 {allowed}）" if allowed else "errors 为空",
        actual=errors,
        detail="" if not unexpected else f"预期外错误: {unexpected}",
    )


def _check_task_order(response: dict) -> CheckResult:
    """
    依赖是真的被遵守：下游任务必须在上游任务完成之后才开始。

    这比 require_dependency_task（只验 depends_on 字段非空）强，
    是"声明了依赖"与"执行时真的尊重了依赖"的区别。
    """

    tasks = {
        str(task.get("id")): task
        for task in (response.get("tasks") or [])
    }

    violations: list[str] = []
    verified: list[str] = []

    for task_id, task in tasks.items():
        for dependency_id in (task.get("depends_on") or []):
            dependency = tasks.get(str(dependency_id))

            if dependency is None:
                violations.append(f"{task_id} 依赖了不存在的 {dependency_id}")
                continue

            start = task.get("started_at")
            dep_end = dependency.get("completed_at")

            if start is None or dep_end is None:
                violations.append(
                    f"{task_id}/{dependency_id} 缺少时间戳 "
                    f"(start={start}, dep_completed={dep_end})"
                )
                continue

            if float(start) < float(dep_end) - TIME_TOLERANCE:
                violations.append(
                    f"{task_id} 在 {dependency_id} 完成前就开始了 "
                    f"({float(dep_end) - float(start):.3f}s 提前)"
                )
            else:
                verified.append(f"{task_id} after {dependency_id}")

    return CheckResult(
        key="require_task_order",
        passed=not violations,
        expected="下游任务在下游依赖完成后才开始",
        actual=verified,
        detail="; ".join(violations),
    )


def _check_concurrency(response: dict) -> CheckResult:
    """
    并发是真的发生：至少存在一对任务的执行时间区间重叠。

    这比 require_parallel_root_tasks（只数根任务个数）强，
    是"声明了两个根任务"与"它们真的同时跑"的区别。
    """

    intervals = task_intervals(response)
    ids = sorted(intervals)

    overlapping: list[str] = []

    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            if _intervals_overlap(intervals[left], intervals[right]):
                overlapping.append(f"{left} || {right}")

    return CheckResult(
        key="require_concurrency",
        passed=bool(overlapping),
        expected="至少一对任务时间区间重叠",
        actual=overlapping or "无重叠",
        detail="" if overlapping else "所有任务都是串行执行的，未观察到并发",
    )


def evaluate_expectation(
    *,
    expect: Expectation,
    response: dict,
    steps_executed: int,
) -> list[CheckResult]:
    """对单次响应执行全部已声明的断言。"""

    checks: list[CheckResult] = []

    answer = str(response.get("answer") or "")
    lower_answer = answer.lower()

    events = collect_events(response)
    agents = collect_agents(response)
    skills = collect_skills(response)
    tools = collect_tools(response)
    tasks = response.get("tasks") or []
    metrics = response.get("metrics") or {}

    # ---------- 路由 ----------

    if expect.task_type_in is not None:
        actual_type = str(response.get("task_type"))
        checks.append(
            CheckResult(
                key="task_type_in",
                passed=actual_type in expect.task_type_in,
                expected=expect.task_type_in,
                actual=actual_type,
                detail=""
                if actual_type in expect.task_type_in
                else f"task_type={actual_type!r} 不在允许列表内",
            )
        )

    if expect.required_agents:
        checks.append(_check_subset("required_agents", expect.required_agents, agents))

    if expect.required_skills:
        checks.append(_check_subset("required_skills", expect.required_skills, skills))

    if expect.required_tools:
        checks.append(_check_subset("required_tools", expect.required_tools, tools))

    if expect.forbidden_agents:
        checks.append(
            _check_forbidden("forbidden_agents", expect.forbidden_agents, agents)
        )

    if expect.forbidden_skills:
        checks.append(
            _check_forbidden("forbidden_skills", expect.forbidden_skills, skills)
        )

    if expect.forbidden_tools:
        checks.append(
            _check_forbidden("forbidden_tools", expect.forbidden_tools, tools)
        )

    # ---------- DAG 形状 ----------

    if expect.min_task_count is not None:
        checks.append(
            CheckResult(
                key="min_task_count",
                passed=len(tasks) >= expect.min_task_count,
                expected=f">= {expect.min_task_count}",
                actual=len(tasks),
                detail=""
                if len(tasks) >= expect.min_task_count
                else f"任务数 {len(tasks)} 少于下限 {expect.min_task_count}",
            )
        )

    if expect.max_task_count is not None:
        checks.append(
            _check_limit("max_task_count", expect.max_task_count, len(tasks))
        )

    if expect.require_dependency_task:
        has_dependency = any(task.get("depends_on") for task in tasks)
        checks.append(
            CheckResult(
                key="require_dependency_task",
                passed=has_dependency,
                expected="至少一个任务带 depends_on",
                actual=[task.get("depends_on") for task in tasks],
                detail="" if has_dependency else "没有任何任务声明依赖",
            )
        )

    if expect.require_parallel_root_tasks:
        root_count = sum(1 for task in tasks if not task.get("depends_on"))
        checks.append(
            CheckResult(
                key="require_parallel_root_tasks",
                passed=root_count >= 2,
                expected=">= 2 个无依赖的根任务",
                actual=root_count,
                detail="" if root_count >= 2 else f"只有 {root_count} 个根任务",
            )
        )

    if expect.require_all_tasks_completed:
        statuses = {
            str(task.get("id")): task.get("status")
            for task in tasks
        }
        not_completed = {
            key: value
            for key, value in statuses.items()
            if value != "completed"
        }
        checks.append(
            CheckResult(
                key="require_all_tasks_completed",
                passed=not not_completed,
                expected="全部任务 status=completed",
                actual=statuses,
                detail="" if not not_completed else f"未完成: {not_completed}",
            )
        )

    # ---------- 时序 ----------

    if expect.require_task_order:
        checks.append(_check_task_order(response))

    if expect.require_concurrency:
        checks.append(_check_concurrency(response))

    # ---------- 事件 ----------

    if expect.required_events:
        checks.append(
            _check_subset("required_events", expect.required_events, events)
        )

    if expect.required_events_any:
        hit = sorted(set(expect.required_events_any) & set(events))
        checks.append(
            CheckResult(
                key="required_events_any",
                passed=bool(hit),
                expected=f"至少出现 {expect.required_events_any}",
                actual=events,
                detail="" if hit else "一个都没出现",
            )
        )

    if expect.require_events_order:
        ordered = _is_subsequence(expect.require_events_order, events)
        checks.append(
            CheckResult(
                key="require_events_order",
                passed=ordered,
                expected=f"{expect.require_events_order} 按序出现",
                actual=events,
                detail="" if ordered else "事件顺序不符合预期（或缺失）",
            )
        )

    # ---------- 答案文本 ----------

    if expect.answer_contains_any:
        hit = [
            keyword
            for keyword in expect.answer_contains_any
            if keyword.lower() in lower_answer
        ]
        checks.append(
            CheckResult(
                key="answer_contains_any",
                passed=bool(hit),
                expected=expect.answer_contains_any,
                actual=hit,
                detail="" if hit else "答案里一个期望关键词都没出现",
            )
        )

    if expect.answer_contains_none_of:
        present = [
            keyword
            for keyword in expect.answer_contains_none_of
            if keyword.lower() in lower_answer
        ]
        checks.append(
            CheckResult(
                key="answer_contains_none_of",
                passed=not present,
                expected=f"不得出现 {expect.answer_contains_none_of}",
                actual=present,
                detail="" if not present else f"出现了不该出现的内容: {present}",
            )
        )

    if expect.min_answer_length is not None:
        checks.append(
            CheckResult(
                key="min_answer_length",
                passed=len(answer) >= expect.min_answer_length,
                expected=f">= {expect.min_answer_length}",
                actual=len(answer),
                detail=""
                if len(answer) >= expect.min_answer_length
                else "答案过短",
            )
        )

    # ---------- 引用 ----------

    citations = count_citations(answer)

    if expect.require_citation is not None:
        checks.append(
            CheckResult(
                key="require_citation",
                passed=bool(citations) is expect.require_citation,
                expected=f"是否带引用 = {expect.require_citation}",
                actual=citations,
                detail=""
                if bool(citations) is expect.require_citation
                else "引用存在性与预期不符",
            )
        )

    if expect.min_citations is not None:
        checks.append(
            CheckResult(
                key="min_citations",
                passed=len(citations) >= expect.min_citations,
                expected=f">= {expect.min_citations}",
                actual=citations,
                detail=""
                if len(citations) >= expect.min_citations
                else f"只有 {len(citations)} 处引用",
            )
        )

    if expect.max_citation_index:
        source_count = retrieved_source_count(response)
        max_index = max(citations) if citations else 0

        if source_count is None:
            checks.append(
                CheckResult(
                    key="max_citation_index",
                    passed=False,
                    expected="能从 tool_results 取到检索条数",
                    actual=None,
                    detail="取不到检索条数，无法校验引用编号",
                )
            )
        else:
            checks.append(
                CheckResult(
                    key="max_citation_index",
                    passed=max_index <= source_count,
                    expected=f"最大引用编号 <= 检索条数 {source_count}",
                    actual=max_index,
                    detail=""
                    if max_index <= source_count
                    else f"引用了不存在的 [Source {max_index}]，实际只有 {source_count} 条",
                )
            )

    # ---------- 原始 trace 文案 ----------

    if expect.require_trace_contains:
        trace_text = "\n".join(str(item) for item in (response.get("trace") or []))
        missing = [
            token
            for token in expect.require_trace_contains
            if token not in trace_text
        ]
        checks.append(
            CheckResult(
                key="require_trace_contains",
                passed=not missing,
                expected=expect.require_trace_contains,
                actual=trace_text,
                detail="" if not missing else f"trace 中缺少: {missing}",
            )
        )

    # ---------- 预算 ----------

    budget_limits = [
        ("max_retries", expect.max_retries, metrics.get("total_retries")),
        ("max_llm_calls", expect.max_llm_calls, metrics.get("total_llm_calls")),
        ("max_input_tokens", expect.max_input_tokens, metrics.get("total_input_tokens")),
        ("max_output_tokens", expect.max_output_tokens, metrics.get("total_output_tokens")),
        ("max_tool_calls", expect.max_tool_calls, metrics.get("total_tool_calls")),
        ("max_latency_ms", expect.max_latency_ms, metrics.get("latency_ms")),
        ("max_cost_usd", expect.max_cost_usd, metrics.get("estimated_cost_usd")),
    ]

    for key, limit, actual in budget_limits:
        if limit is None:
            continue
        if actual is None:
            checks.append(
                CheckResult(
                    key=key,
                    passed=False,
                    expected=limit,
                    actual=None,
                    detail=f"metrics 里取不到 {key}",
                )
            )
            continue
        checks.append(_check_limit(key, limit, float(actual)))

    # ---------- 记忆 ----------

    if expect.require_memory_decision_in:
        decision = memory_decision(response)
        allowed = [d.upper() for d in expect.require_memory_decision_in]
        checks.append(
            CheckResult(
                key="require_memory_decision_in",
                passed=decision in allowed,
                expected=allowed,
                actual=decision,
                detail=""
                if decision in allowed
                else f"记忆决策 {decision!r} 不在预期内",
            )
        )

    if expect.require_memory_fast_path is not None:
        present = "memory_fast_path" in events
        checks.append(
            CheckResult(
                key="require_memory_fast_path",
                passed=present is expect.require_memory_fast_path,
                expected=f"memory_fast_path 出现 = {expect.require_memory_fast_path}",
                actual=present,
                detail=""
                if present is expect.require_memory_fast_path
                else "记忆快路径行为与预期不符",
            )
        )

    # ---------- 执行完整性 ----------

    if expect.min_steps is not None:
        checks.append(
            CheckResult(
                key="min_steps",
                passed=steps_executed >= expect.min_steps,
                expected=f">= {expect.min_steps}",
                actual=steps_executed,
                detail=""
                if steps_executed >= expect.min_steps
                else f"只执行了 {steps_executed} 步，运行被提前中断",
            )
        )

    # ---------- 错误 ----------

    checks.append(_check_no_errors(expect, response))

    return checks
