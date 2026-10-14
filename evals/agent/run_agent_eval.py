"""
Agent Evaluation —— CLI 入口。

用法：

    # 只跑离线专项（秒级，无 LLM，可进 CI）
    python evals/agent/run_agent_eval.py --scope component

    # 只跑端到端，不启用 judge
    python evals/agent/run_agent_eval.py --scope e2e --no-judge

    # 全量
    python evals/agent/run_agent_eval.py --scope all

    # 只跑某个维度
    python evals/agent/run_agent_eval.py --only dag_runtime

    # 抖动用例复现
    python evals/agent/run_agent_eval.py --only memory --repeat 3

退出码：确定性断言全通过 -> 0，否则 1。
judge 默认不影响退出码，除非加 --judge-strict。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 保证从仓库根目录导入 app / evals
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evals.agent.assertions import (          # noqa: E402
    evaluate_expectation,
    summarize_observation,
)
from evals.agent.client import (              # noqa: E402
    ChatClient,
    ChatClientError,
)
from evals.agent.report import (              # noqa: E402
    build_run_result,
    print_report,
    write_json,
)
from evals.agent.schema import (              # noqa: E402
    CaseResult,
    CheckResult,
    EvalCase,
    EvalDataset,
    StepResult,
)

DEFAULT_DATASET = PROJECT_ROOT / "evals" / "agent" / "datasets" / "agent_cases.json"
DEFAULT_OUT = PROJECT_ROOT / "evals" / "agent" / "results"

JUDGE_PASS_THRESHOLD = 4.0


# ============================================================
# 数据集
# ============================================================

def load_dataset(path: Path) -> EvalDataset:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EvalDataset.model_validate(payload)


def dataset_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


# ============================================================
# 过滤
# ============================================================

def matches_only(case: EvalCase, selectors: list[str]) -> bool:
    if not selectors:
        return True

    haystack = {case.dimension, case.id, *case.tags}

    return bool(haystack & set(selectors))


# ============================================================
# 单案例执行
# ============================================================

def run_case(
    *,
    client: ChatClient,
    case: EvalCase,
    run_id: str,
) -> tuple[CaseResult, dict | None]:
    """
    执行一个端到端案例，逐步断言。

    返回 (CaseResult, 最后一步的原始响应)。
    """

    started = time.perf_counter()

    # shared 模式的 session_id 由本次 run 派生，保证跨 run 互不污染；
    # 同时因为是拿 run_id 生成的，天然不会读到上一次评测留下的记忆。
    session_id = (
        f"eval-{run_id}-{case.id}"
        if case.session_mode == "shared"
        else None
    )

    step_results: list[StepResult] = []
    executed = 0
    last_response: dict | None = None

    for index, step in enumerate(case.steps, start=1):
        is_last = index == len(case.steps)

        try:
            response = client.chat(step.message, session_id=session_id)
        except ChatClientError as exc:
            step_results.append(
                StepResult(
                    step=index,
                    message=step.message,
                    failed=True,
                    error=str(exc),
                )
            )
            break

        executed = index
        last_response = response

        # 步级 expect 优先；最后一步若没写步级，则用案例级 expect
        expect = step.expect
        if expect is None and is_last:
            expect = case.expect

        checks = (
            evaluate_expectation(
                expect=expect,
                response=response,
                steps_executed=executed,
            )
            if expect is not None
            else []
        )

        metrics = response.get("metrics") or {}

        step_results.append(
            StepResult(
                step=index,
                message=step.message,
                failed=any(not check.passed for check in checks),
                checks=checks,
                latency_ms=float(metrics.get("latency_ms", 0.0) or 0.0),
            )
        )

    # 中途抛错导致没跑满步数 —— 显式记为失败，而不是静默少跑
    if executed < len(case.steps) and step_results:
        step_results[-1].checks.append(
            CheckResult(
                key="run_completed_all_steps",
                passed=False,
                expected=len(case.steps),
                actual=executed,
                detail="运行中途中断，后续步骤未执行",
            )
        )
        step_results[-1].failed = True

    failed_keys = [
        check.key
        for step in step_results
        for check in step.checks
        if not check.passed
    ]

    result = CaseResult(
        id=case.id,
        name=case.name,
        dimension=case.dimension,
        tags=case.tags,
        kind="e2e",
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        passed=not failed_keys,
        steps=step_results,
        failed_keys=failed_keys,
        observed=summarize_observation(last_response) if last_response else {},
        answer_excerpt=str((last_response or {}).get("answer", ""))[:600],
    )

    return result, last_response


# ============================================================
# judge
# ============================================================

def apply_judge(
    *,
    judge,
    case: EvalCase,
    result: CaseResult,
    response: dict | None,
) -> None:
    config = case.judge

    if config is None or not config.enabled or response is None:
        return

    result.judge = judge.judge(
        query=case.steps[-1].message,
        response=response,
        dimensions=config.dimensions,
        evidence_from=config.evidence_from,
    )


def judge_failed(result: CaseResult) -> bool:
    scores = (result.judge or {}).get("scores") or {}

    if not scores:
        return False

    return (sum(scores.values()) / len(scores)) < JUDGE_PASS_THRESHOLD


# ============================================================
# memory 清理
# ============================================================

def cleanup_sessions(session_ids: list[str]) -> None:
    """删除本次 run 产生的记忆记录（SQLite + Chroma）。"""

    if not session_ids:
        return

    try:
        from app.memory.sqlite_store import memory_store
        from app.memory.vector_store import semantic_memory_store
    except Exception:
        return

    removed = 0

    for session_id in session_ids:
        try:
            records = memory_store.get_session_memories(session_id)
        except Exception:
            continue

        for record in records:
            try:
                semantic_memory_store.delete(record.id)
            except Exception:
                pass

        try:
            memory_store.clear_session(session_id)
            removed += len(records)
        except Exception:
            pass

    print(f"[cleanup] 已清理 {removed} 条记忆记录")


# ============================================================
# main
# ============================================================

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Agent Evaluation runner",
    )

    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--scope",
        choices=["e2e", "component", "all"],
        default="all",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="DIMENSION|TAG|ID",
        help="只跑匹配的案例，可重复",
    )
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--judge-strict", action="store_true")
    parser.add_argument("--show-all-checks", action="store_true")
    parser.add_argument("--cleanup-memory", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument(
        "--api-key",
        default=None,
        help=(
            "对 demo 模式服务跑评测时必填，"
            "会作为 X-API-Key 发送。dev 模式留空即可。"
        ),
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    run_started = time.perf_counter()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamp = datetime.now().isoformat(timespec="seconds")

    dataset = load_dataset(args.cases)

    selected = [
        case for case in dataset.cases
        if matches_only(case, args.only)
    ]

    cases_to_run: list[EvalCase] = []
    for _ in range(max(1, args.repeat)):
        cases_to_run.extend(selected)

    # ---------- 被测系统模型名（仅用于记录）----------

    system_model = "unknown"

    try:
        from app.core.config import settings

        system_model = settings.llm_model
    except Exception:
        pass

    # ---------- 离线专项 ----------

    results: list[CaseResult] = []

    if args.scope in {"component", "all"}:
        from evals.agent.component_checks import run_component_cases

        component_results = run_component_cases()

        if args.only:
            component_results = [
                case for case in component_results
                if {case.dimension, case.id, *case.tags} & set(args.only)
            ]

        results.extend(component_results)

    # ---------- 端到端 ----------

    sessions_used: list[str] = []
    judge_summary: dict | None = None

    if args.scope in {"e2e", "all"} and cases_to_run:

        client = ChatClient(
            args.base_url,
            timeout_seconds=args.timeout,
            api_key=args.api_key,
        )

        try:
            if not args.skip_preflight:
                print(f"[preflight] 检查 {args.base_url} ...")
                client.preflight()
                print("[preflight] ok")

            judge = None

            if not args.no_judge:
                from evals.agent.judge import Judge

                judge = Judge()

            total = len(cases_to_run)

            for index, case in enumerate(cases_to_run, start=1):
                print(f"[{index}/{total}] {case.id} {case.name}")

                if case.session_mode == "shared":
                    sessions_used.append(f"eval-{run_id}-{case.id}")

                result, response = run_case(
                    client=client,
                    case=case,
                    run_id=run_id,
                )

                if judge is not None:
                    apply_judge(
                        judge=judge,
                        case=case,
                        result=result,
                        response=response,
                    )

                if args.judge_strict and judge_failed(result):
                    result.passed = False
                    result.failed_keys.append("judge_score_below_threshold")

                results.append(result)

                status = "PASS" if result.passed else "FAIL"

                print(
                    f"        {status}  {result.elapsed_ms} ms"
                    + (
                        f"  failed={result.failed_keys}"
                        if result.failed_keys
                        else ""
                    )
                )

            judge_summary = judge.summary() if judge is not None else None

        finally:
            client.close()

        if args.cleanup_memory:
            cleanup_sessions(sessions_used)

    # ---------- 汇总输出 ----------

    if not results:
        print("没有匹配任何案例。检查 --scope / --only / 数据集路径。")
        return 1

    e2e_ran = any(case.kind == "e2e" for case in results)

    run_meta = {
        "timestamp": timestamp,
        "run_id": run_id,
        "base_url": args.base_url,
        "scope": args.scope,
        "only": args.only,
        "repeat": args.repeat,
        "case_count": len(results),
        "e2e_case_count": sum(1 for case in results if case.kind == "e2e"),
        "dataset": str(args.cases),
        # 只有真跑了 e2e 才记数据集指纹。component-only 时它无从比较，
        # 留着只会让两份 scope 不同的结果看起来可以逐字节对比。
        "dataset_version": dataset.version if e2e_ran else None,
        "dataset_sha256": dataset_fingerprint(args.cases) if e2e_ran else None,
        "system_model": system_model,
        "git_commit": git_commit(),
        "elapsed_ms": round((time.perf_counter() - run_started) * 1000, 2),
    }

    run_result = build_run_result(
        cases=results,
        run_meta=run_meta,
        judge_summary=judge_summary,
    )

    print_report(run_result, show_all_checks=args.show_all_checks)

    path = write_json(run_result, args.out)
    print(f"\n结果已写入: {path}")

    return 0 if run_result.summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
