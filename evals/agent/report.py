"""
Agent Evaluation —— 结果输出。

控制台给"人快速看"，JSON 给"机器回归和趋势对比"。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.agent.schema import CaseResult, RunResult

LINE = "=" * 78
THIN = "-" * 78


def _as_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj


def build_run_result(
    *,
    cases: list[CaseResult],
    run_meta: dict,
    judge_summary: dict | None = None,
) -> RunResult:
    """把案例结果汇总成一份完整的 RunResult。"""

    by_dimension: dict[str, dict[str, int]] = {}

    for case in cases:
        bucket = by_dimension.setdefault(
            case.dimension, {"passed": 0, "total": 0}
        )
        bucket["total"] += 1
        if case.passed:
            bucket["passed"] += 1

    latencies = sorted(
        case.elapsed_ms for case in cases if case.kind == "e2e"
    )

    def percentile(values: list[float], ratio: float) -> float:
        if not values:
            return 0.0
        index = min(int(len(values) * ratio), len(values) - 1)
        return round(values[index], 2)

    total_tokens = 0
    total_cost = 0.0

    for case in cases:
        metrics = (case.observed or {}).get("metrics") or {}
        total_tokens += int(metrics.get("total_input_tokens", 0) or 0)
        total_tokens += int(metrics.get("total_output_tokens", 0) or 0)
        total_cost += float(metrics.get("estimated_cost_usd", 0.0) or 0.0)

    judge_scores: dict[str, list[float]] = {}

    for case in cases:
        for dim, score in ((case.judge or {}).get("scores") or {}).items():
            judge_scores.setdefault(dim, []).append(float(score))

    judge_avg = {
        dim: round(sum(values) / len(values), 3)
        for dim, values in judge_scores.items()
        if values
    }

    passed = sum(1 for case in cases if case.passed)
    failed = len(cases) - passed

    summary = {
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
        "by_dimension": by_dimension,
        "judge_avg": judge_avg,
        "total_tokens": total_tokens,
        "system_estimated_cost_usd": round(total_cost, 8),
        "latency_p50_ms": percentile(latencies, 0.5),
        "latency_p95_ms": percentile(latencies, 0.95),
        "failures": [
            {
                "id": case.id,
                "dimension": case.dimension,
                "failed_keys": case.failed_keys,
                "error": case.error,
            }
            for case in cases
            if not case.passed
        ],
    }

    if judge_summary:
        summary["judge"] = judge_summary

    return RunResult(run=run_meta, cases=cases, summary=summary)


def print_report(result: RunResult, *, show_all_checks: bool = False) -> None:
    """控制台报告。"""

    print()
    print(LINE)
    print("AGENT EVALUATION REPORT")
    print(LINE)

    run = result.run

    print(f"  时间        : {run.get('timestamp')}")
    print(f"  服务        : {run.get('base_url')}")
    print(f"  系统模型    : {run.get('system_model')}")
    fingerprint = (run.get("dataset_sha256") or "")[:12] or "—"

    print(
        f"  数据集      : {fingerprint}"
        f"  (e2e {run.get('e2e_case_count', 0)} 条 / 合计 {run.get('case_count')} 条)"
    )
    print(f"  scope       : {run.get('scope')}")
    print(f"  git         : {run.get('git_commit')}")
    print(f"  总耗时      : {run.get('elapsed_ms')} ms")

    # ---------- 分维度 ----------

    print()
    print(THIN)
    print(f"{'维度':<26}{'通过':>8}{'总数':>8}{'通过率':>10}")
    print(THIN)

    by_dimension = sorted(
        result.summary.get("by_dimension", {}).items(),
        key=lambda item: (item[1]["passed"] / item[1]["total"] if item[1]["total"] else 0),
    )

    for dimension, bucket in by_dimension:
        total = bucket["total"]
        passed = bucket["passed"]
        rate = passed / total if total else 0.0
        flag = "  " if passed == total else " <"
        print(f"{dimension:<26}{passed:>8}{total:>8}{rate:>9.1%}{flag}")

    print(THIN)

    summary = result.summary

    print(
        f"{'合计':<26}{summary['passed']:>8}{summary['total']:>8}"
        f"{summary['pass_rate']:>9.1%}"
    )

    # ---------- 预算 ----------

    print()
    print(THIN)
    print("预算与耗时")
    print(THIN)
    print(f"  总 token（被测系统）: {summary.get('total_tokens')}")
    print(f"  估算成本（被测系统）: {summary.get('system_estimated_cost_usd')} USD")

    judge = summary.get("judge")

    if judge:
        print(f"  估算成本（judge）   : {judge.get('cost_usd')} USD "
              f"({judge.get('calls')} 次调用, {judge.get('errors')} 次失败)")

    print(f"  e2e 延迟 p50/p95    : "
          f"{summary.get('latency_p50_ms')} / {summary.get('latency_p95_ms')} ms")

    if summary.get("judge_avg"):
        print()
        print(f"  judge 均分          : {summary['judge_avg']}")

    # ---------- 失败明细 ----------

    failures = [
        case for case in result.cases if not case.passed
    ]

    if failures:
        print()
        print(THIN)
        print(f"失败明细（{len(failures)} 条）")
        print(THIN)

        for case in failures:
            print(f"\n[{case.id}] {case.name}   ({case.dimension})")

            if case.error:
                print(f"    执行出错: {case.error}")

            for step in case.steps:
                for check in step.checks:
                    if check.passed:
                        continue
                    print(f"    第 {step.step} 步 · {check.key}")
                    print(f"        期望: {_short(check.expected)}")
                    print(f"        实际: {_short(check.actual)}")
                    if check.detail:
                        print(f"        说明: {check.detail}")

            for step in case.steps:
                if step.error:
                    print(f"    第 {step.step} 步异常: {step.error}")

    elif result.cases:
        print("\n全部通过。")

    print()
    print(LINE)
    print(
        f"{'PASS' if summary['failed'] == 0 else 'FAIL'} — "
        f"{summary['passed']} passed / {summary['total']} total"
    )
    print(LINE)

    if show_all_checks:
        print("\n全部断言明细：")
        for case in result.cases:
            print(f"\n[{case.id}]")
            for step in case.steps:
                for check in step.checks:
                    mark = "ok  " if check.passed else "FAIL"
                    print(f"  {mark} {check.key} => {_short(check.actual)}")


def _short(value: Any, limit: int = 200) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + f"...(+{len(text) - limit})"


def write_json(result: RunResult, out_dir: Path) -> Path:
    """落盘结果 JSON。"""

    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"agent_eval_{timestamp}.json"

    payload = {
        "run": result.run,
        "cases": [_as_dict(case) for case in result.cases],
        "summary": result.summary,
    }

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return path
