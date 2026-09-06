from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


# ============================================================
# Paths
# ============================================================

TEST_DIR = Path(__file__).resolve().parent

CONFIG_FILE = (
    TEST_DIR
    / "demo_cases.json"
)

RESULT_DIR = (
    TEST_DIR
    / "results"
)


# ============================================================
# Utilities
# ============================================================

def load_config() -> dict[str, Any]:

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def get_agents(
    response: dict[str, Any]
) -> set[str]:

    agents = set()

    for task in response.get(
        "tasks",
        [],
    ):
        agent = task.get("agent")

        if agent:
            agents.add(agent)

    return agents


def get_skills(
    response: dict[str, Any]
) -> set[str]:

    skills = set()

    for task in response.get(
        "tasks",
        [],
    ):
        skill = task.get("skill")

        if skill:
            skills.add(skill)

    return skills


def get_tools(
    response: dict[str, Any]
) -> set[str]:

    tools = set()

    for task in response.get(
        "tasks",
        [],
    ):

        for call in task.get(
            "tool_calls",
            [],
        ):

            tool = call.get("tool")

            if tool:
                tools.add(tool)

    return tools


def get_events(
    response: dict[str, Any]
) -> set[str]:

    return {
        event.get("event_type")
        for event
        in response.get(
            "structured_trace",
            [],
        )
        if event.get("event_type")
    }


# ============================================================
# Assertions
# ============================================================

def check_response(
    response: dict[str, Any],
    expect: dict[str, Any],
) -> list[str]:

    failures: list[str] = []

    # --------------------------------------------------------
    # task_type
    # --------------------------------------------------------

    allowed_task_types = expect.get(
        "task_type_in"
    )

    if allowed_task_types:

        actual = response.get(
            "task_type"
        )

        if actual not in allowed_task_types:

            failures.append(
                (
                    f"task_type expected "
                    f"{allowed_task_types}, "
                    f"got {actual}"
                )
            )

    # --------------------------------------------------------
    # Agents
    # --------------------------------------------------------

    required_agents = set(
        expect.get(
            "required_agents",
            [],
        )
    )

    actual_agents = get_agents(
        response
    )

    missing_agents = (
        required_agents
        - actual_agents
    )

    if missing_agents:

        failures.append(
            "missing agents: "
            + ", ".join(
                sorted(
                    missing_agents
                )
            )
        )

    # --------------------------------------------------------
    # Skills
    # --------------------------------------------------------

    required_skills = set(
        expect.get(
            "required_skills",
            [],
        )
    )

    actual_skills = get_skills(
        response
    )

    missing_skills = (
        required_skills
        - actual_skills
    )

    if missing_skills:

        failures.append(
            "missing skills: "
            + ", ".join(
                sorted(
                    missing_skills
                )
            )
        )

    # --------------------------------------------------------
    # Tools
    # --------------------------------------------------------

    required_tools = set(
        expect.get(
            "required_tools",
            [],
        )
    )

    actual_tools = get_tools(
        response
    )

    missing_tools = (
        required_tools
        - actual_tools
    )

    if missing_tools:

        failures.append(
            "missing tools: "
            + ", ".join(
                sorted(
                    missing_tools
                )
            )
        )

    # --------------------------------------------------------
    # Trace Events
    # --------------------------------------------------------

    events = get_events(
        response
    )

    required_events = set(
        expect.get(
            "required_events",
            [],
        )
    )

    missing_events = (
        required_events
        - events
    )

    if missing_events:

        failures.append(
            "missing trace events: "
            + ", ".join(
                sorted(
                    missing_events
                )
            )
        )

    required_events_any = set(
        expect.get(
            "required_events_any",
            [],
        )
    )

    if (
        required_events_any
        and
        not (
            events
            & required_events_any
        )
    ):

        failures.append(
            (
                "none of required events "
                f"found: "
                f"{sorted(required_events_any)}"
            )
        )

    # --------------------------------------------------------
    # Answer
    # --------------------------------------------------------

    answer = str(
        response.get(
            "answer",
            ""
        )
    )

    contains_any = expect.get(
        "answer_contains_any",
        [],
    )

    if contains_any:

        matched = any(
            keyword.lower()
            in answer.lower()

            for keyword
            in contains_any
        )

        if not matched:

            failures.append(
                (
                    "answer does not contain "
                    f"any expected keyword: "
                    f"{contains_any}"
                )
            )

    # --------------------------------------------------------
    # Tasks
    # --------------------------------------------------------

    tasks = response.get(
        "tasks",
        [],
    )

    min_task_count = expect.get(
        "min_task_count"
    )

    if (
        min_task_count is not None
        and len(tasks)
        < min_task_count
    ):

        failures.append(
            (
                f"expected >= "
                f"{min_task_count} tasks, "
                f"got {len(tasks)}"
            )
        )

    # --------------------------------------------------------
    # Dependency
    # --------------------------------------------------------

    if expect.get(
        "require_dependency_task"
    ):

        has_dependency = any(
            bool(
                task.get(
                    "depends_on"
                )
            )
            for task in tasks
        )

        if not has_dependency:

            failures.append(
                (
                    "expected at least one "
                    "dependency task"
                )
            )

    # --------------------------------------------------------
    # Parallel roots
    # --------------------------------------------------------

    if expect.get(
        "require_parallel_root_tasks"
    ):

        root_tasks = [
            task
            for task
            in tasks
            if not task.get(
                "depends_on"
            )
        ]

        if len(root_tasks) < 2:

            failures.append(
                (
                    "expected >= 2 "
                    "independent root tasks"
                )
            )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    metrics = response.get(
        "metrics",
        {},
    )

    max_retries = expect.get(
        "max_retries"
    )

    if max_retries is not None:

        retries = metrics.get(
            "total_retries",
            0,
        )

        if retries > max_retries:

            failures.append(
                (
                    f"retries expected <= "
                    f"{max_retries}, "
                    f"got {retries}"
                )
            )

    max_llm_calls = expect.get(
        "max_llm_calls"
    )

    if max_llm_calls is not None:

        calls = metrics.get(
            "total_llm_calls",
            0,
        )

        if calls > max_llm_calls:

            failures.append(
                (
                    f"LLM calls expected <= "
                    f"{max_llm_calls}, "
                    f"got {calls}"
                )
            )

    max_input_tokens = expect.get(
        "max_input_tokens"
    )

    if max_input_tokens is not None:

        tokens = metrics.get(
            "total_input_tokens",
            0,
        )

        if tokens > max_input_tokens:

            failures.append(
                (
                    f"input tokens expected <= "
                    f"{max_input_tokens}, "
                    f"got {tokens}"
                )
            )

    # --------------------------------------------------------
    # Errors
    # --------------------------------------------------------

    errors = response.get(
        "errors",
        [],
    )

    if errors:

        failures.append(
            f"workflow contains errors: {errors}"
        )

    return failures


# ============================================================
# HTTP
# ============================================================

def call_chat(
    client: httpx.Client,
    url: str,
    message: str,
    session_id: str | None = None,
) -> dict[str, Any]:

    payload: dict[str, Any] = {
        "message": message,
    }

    if session_id:
        payload[
            "session_id"
        ] = session_id

    response = client.post(
        url,
        json=payload,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# Run Case
# ============================================================

def run_case(
    client: httpx.Client,
    url: str,
    case: dict[str, Any],
) -> dict[str, Any]:

    case_started = (
        time.perf_counter()
    )

    session_id = None

    step_results = []

    failures = []

    steps = case.get(
        "steps",
        [],
    )

    reuse_session = case.get(
        "reuse_session",
        False,
    )

    for index, step in enumerate(
        steps,
        start=1,
    ):

        message = step[
            "message"
        ]

        print(
            f"    Step {index}: "
            f"{message[:60]}"
        )

        try:

            response = call_chat(
                client=client,
                url=url,
                message=message,
                session_id=(
                    session_id
                    if reuse_session
                    else None
                ),
            )

        except Exception as exc:

            failures.append(
                (
                    f"step {index} "
                    f"request failed: {exc}"
                )
            )

            break

        returned_session = (
            response.get(
                "session_id"
            )
        )

        if (
            reuse_session
            and returned_session
        ):

            session_id = (
                returned_session
            )

        step_results.append(
            response
        )

    # --------------------------------------------------------
    # Validate final response
    # --------------------------------------------------------

    if step_results:

        final_response = (
            step_results[-1]
        )

        expectation_failures = (
            check_response(
                final_response,
                case.get(
                    "expect",
                    {},
                ),
            )
        )

        failures.extend(
            expectation_failures
        )

    elapsed_ms = (
        time.perf_counter()
        - case_started
    ) * 1000

    return {
        "id":
            case["id"],

        "name":
            case.get("name"),

        "passed":
            len(failures) == 0,

        "failures":
            failures,

        "elapsed_ms":
            round(
                elapsed_ms,
                2,
            ),

        "steps":
            step_results,
    }


# ============================================================
# Main
# ============================================================

def main() -> int:

    config = load_config()

    base_url = (
        config["base_url"]
        .rstrip("/")
    )

    endpoint = (
        config["endpoint"]
    )

    url = (
        base_url
        + endpoint
    )

    timeout_seconds = (
        config.get(
            "timeout_seconds",
            120,
        )
    )

    cases = config.get(
        "cases",
        [],
    )

    print()
    print(
        "Enterprise Multi-Agent "
        "Regression Suite"
    )
    print(
        "=" * 60
    )

    print(
        f"Target: {url}"
    )

    print(
        f"Cases: {len(cases)}"
    )

    print(
        "=" * 60
    )
    print()

    suite_started = (
        time.perf_counter()
    )

    results = []

    with httpx.Client(
        timeout=timeout_seconds
    ) as client:

        for case in cases:

            print(
                f"[RUN] "
                f"{case['id']} "
                f"- {case.get('name', '')}"
            )

            result = run_case(
                client=client,
                url=url,
                case=case,
            )

            results.append(
                result
            )

            if result["passed"]:

                print(
                    f"[PASS] "
                    f"{case['id']} "
                    f"({result['elapsed_ms']} ms)"
                )

            else:

                print(
                    f"[FAIL] "
                    f"{case['id']}"
                )

                for failure in (
                    result["failures"]
                ):

                    print(
                        f"       - {failure}"
                    )

            print()

    suite_elapsed = (
        time.perf_counter()
        - suite_started
    )

    passed = sum(
        1
        for result
        in results
        if result["passed"]
    )

    failed = (
        len(results)
        - passed
    )

    # ========================================================
    # Save Result
    # ========================================================

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    result_file = (
        RESULT_DIR
        / f"regression_{timestamp}.json"
    )

    output = {
        "timestamp":
            timestamp,

        "target":
            url,

        "total":
            len(results),

        "passed":
            passed,

        "failed":
            failed,

        "elapsed_seconds":
            round(
                suite_elapsed,
                2,
            ),

        "results":
            results,
    }

    with open(
        result_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # ========================================================
    # Summary
    # ========================================================

    print(
        "=" * 60
    )

    print(
        "Regression Summary"
    )

    print(
        "=" * 60
    )

    for result in results:

        status = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

        print(
            f"{result['id']:<30} "
            f"{status}"
        )

    print(
        "-" * 60
    )

    print(
        f"{passed} passed / "
        f"{len(results)} total"
    )

    print(
        f"Total time: "
        f"{suite_elapsed:.2f}s"
    )

    print(
        f"Result: {result_file}"
    )

    print(
        "=" * 60
    )

    return (
        0
        if failed == 0
        else 1
    )


if __name__ == "__main__":

    sys.exit(
        main()
    )
