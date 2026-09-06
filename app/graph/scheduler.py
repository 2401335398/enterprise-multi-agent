import asyncio
import time
from copy import deepcopy

from app.agents.registry import AGENT_REGISTRY
from app.graph.state import AgentState
from app.observability.tracer import tracer


MAX_RETRIES = 2
TASK_TIMEOUT_SECONDS = 30


def dependencies_completed(
    task: dict,
    task_map: dict[str, dict],
) -> bool:
    """
    A task is ready only when all dependencies exist and completed.
    """

    for dependency_id in task.get(
        "depends_on",
        [],
    ):
        dependency = task_map.get(
            dependency_id
        )

        if dependency is None:
            return False

        if (
            dependency.get("status")
            != "completed"
        ):
            return False

    return True


async def execute_single_task(
    task: dict,
    state: AgentState,
    task_results: dict[str, str],
) -> dict:
    """
    Execute one Agent task using an isolated state snapshot.
    """

    agent_name = task["agent"]

    agent = AGENT_REGISTRY.get(
        agent_name
    )

    if agent is None:
        raise ValueError(
            f"Unknown agent: {agent_name}"
        )

    dependency_results = {
        dependency_id:
            task_results[dependency_id]

        for dependency_id
        in task.get(
            "depends_on",
            [],
        )

        if dependency_id
        in task_results
    }

    local_state = deepcopy(
        state
    )

    local_state[
        "current_task"
    ] = task

    local_state[
        "dependency_results"
    ] = dependency_results

    result = await agent.run(
        local_state
    )

    print(
        f"\n===== AGENT RESULT "
        f"{task['id']} ====="
    )
    print(
        "agent:",
        agent_name
    )
    print(
        "result:",
        result
    )
    print(
        "================================\n"
    )

    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            f"Agent {agent_name} returned "
            f"non-dict result: {result}"
        )

    if "result" not in result:
        raise ValueError(
            f"Agent {agent_name} returned "
            f"invalid result: {result}"
        )

    return {
        "content":
            result["result"],

        "skill":
            result.get(
                "skill"
            ),

        "tool_calls":
            result.get(
                "tool_calls",
                [],
            ),

        "tool_results":
            result.get(
                "tool_results",
                [],
            ),
    }


async def execute_with_retry(
    task: dict,
    state: AgentState,
    task_results: dict[str, str],
) -> dict:
    """
    Task runtime:
    - timeout
    - retry
    - latency
    """

    total_started_at = (
        time.perf_counter()
    )

    last_error = None
    last_timeout = False
    last_started_at = None
    last_completed_at = None

    for attempt in range(
        MAX_RETRIES + 1
    ):
        try:
            started_at = (
                time.perf_counter()
            )

            last_started_at = started_at

            result = await asyncio.wait_for(
                execute_single_task(
                    task=task,
                    state=state,
                    task_results=task_results,
                ),
                timeout=(
                    TASK_TIMEOUT_SECONDS
                ),
            )

            completed_at = (
                time.perf_counter()
            )

            last_completed_at = (
                completed_at
            )

            total_latency_ms = (
                completed_at
                - total_started_at
            ) * 1000

            return {
                "success":
                    True,

                "result":
                    result,

                "attempts":
                    attempt + 1,

                "started_at":
                    started_at,

                "completed_at":
                    completed_at,

                "latency_ms":
                    total_latency_ms,

                "timeout":
                    False,
            }

        except asyncio.TimeoutError:
            last_completed_at = (
                time.perf_counter()
            )

            last_timeout = True

            last_error = (
                f"Task timeout after "
                f"{TASK_TIMEOUT_SECONDS}s"
            )

        except Exception as exc:
            last_completed_at = (
                time.perf_counter()
            )

            last_timeout = False

            last_error = str(
                exc
            )

        if attempt < MAX_RETRIES:
            tracer.record(
                event_type="task_retry",
                workflow_id=state.get(
                    "workflow_id"
                ),
                task_id=task.get(
                    "id"
                ),
                agent=task.get(
                    "agent"
                ),
                success=False,
                metadata={
                    "attempt":
                        attempt + 1,
                    "error":
                        last_error,
                    "timeout":
                        last_timeout,
                },
            )

            await asyncio.sleep(
                attempt + 1
            )

    total_latency_ms = (
        time.perf_counter()
        - total_started_at
    ) * 1000

    return {
        "success":
            False,

        "error":
            last_error,

        "attempts":
            MAX_RETRIES + 1,

        "started_at":
            last_started_at,

        "completed_at":
            last_completed_at,

        "latency_ms":
            total_latency_ms,

        "timeout":
            last_timeout,
    }


def _extract_tool_names(
    tool_calls: list,
) -> list[str]:
    names: list[str] = []

    for call in tool_calls:
        if isinstance(
            call,
            dict,
        ):
            name = call.get(
                "tool"
            )
        else:
            name = getattr(
                call,
                "tool",
                None,
            )

        if name:
            names.append(
                str(name)
            )

    return names


async def scheduler_node(
    state: AgentState,
) -> dict:
    """
    Deterministic DAG Scheduler.
    """

    print(
        "\n======================================"
    )
    print(
        "V0.9 SCHEDULER IS RUNNING"
    )
    print(
        "======================================\n"
    )

    workflow_id = state.get(
        "workflow_id"
    )

    tasks = deepcopy(
        state["tasks"]
    )

    task_results = dict(
        state.get(
            "task_results",
            {},
        )
    )

    messages: list[str] = []
    errors: list[str] = []

    task_map = {
        task["id"]:
            task

        for task
        in tasks
    }

    while True:
        pending_tasks = [
            task

            for task
            in tasks

            if task.get(
                "status"
            ) == "pending"
        ]

        if not pending_tasks:
            break

        ready_tasks = [
            task

            for task
            in pending_tasks

            if dependencies_completed(
                task,
                task_map,
            )
        ]

        if not ready_tasks:
            unresolved = [
                task["id"]
                for task
                in pending_tasks
            ]

            error = (
                "No executable tasks found. "
                "Possible DAG cycle, missing dependency, "
                "or failed upstream dependency: "
                f"{unresolved}"
            )

            errors.append(
                error
            )

            tracer.record(
                event_type="scheduler_stalled",
                workflow_id=workflow_id,
                success=False,
                metadata={
                    "unresolved_tasks":
                        unresolved,
                    "error":
                        error,
                },
            )

            break

        for task in ready_tasks:
            task[
                "status"
            ] = "running"

            messages.append(
                f"Task {task['id']} "
                f"started by "
                f"{task['agent']}"
            )

            tracer.record(
                event_type="task_started",
                workflow_id=workflow_id,
                task_id=task["id"],
                agent=task["agent"],
                success=True,
                metadata={
                    "depends_on":
                        task.get(
                            "depends_on",
                            [],
                        )
                },
            )

        executions = [
            execute_with_retry(
                task=task,
                state=state,
                task_results=task_results,
            )

            for task
            in ready_tasks
        ]

        execution_results = (
            await asyncio.gather(
                *executions
            )
        )

        for (
            task,
            execution,
        ) in zip(
            ready_tasks,
            execution_results,
        ):
            latency_ms = (
                execution.get(
                    "latency_ms"
                )
            )

            task[
                "started_at"
            ] = execution.get(
                "started_at"
            )

            task[
                "completed_at"
            ] = execution.get(
                "completed_at"
            )

            task[
                "latency_ms"
            ] = (
                round(
                    latency_ms,
                    2,
                )
                if latency_ms
                is not None
                else None
            )

            task[
                "retry_count"
            ] = (
                execution[
                    "attempts"
                ]
                - 1
            )

            if execution[
                "success"
            ]:
                agent_result = (
                    execution[
                        "result"
                    ]
                )

                task_content = (
                    agent_result[
                        "content"
                    ]
                )

                skill_name = (
                    agent_result.get(
                        "skill"
                    )
                )

                tool_calls = (
                    agent_result.get(
                        "tool_calls",
                        [],
                    )
                )

                tool_results = (
                    agent_result.get(
                        "tool_results",
                        [],
                    )
                )

                task[
                    "status"
                ] = "completed"

                task[
                    "result"
                ] = task_content

                task[
                    "skill"
                ] = skill_name

                task[
                    "tool_calls"
                ] = tool_calls

                task[
                    "tool_results"
                ] = tool_results

                task_results[
                    task["id"]
                ] = task_content

                tool_names = (
                    _extract_tool_names(
                        tool_calls
                    )
                )

                if skill_name:
                    tool_text = (
                        ", ".join(
                            tool_names
                        )
                        if tool_names
                        else "none"
                    )

                    messages.append(
                        f"Task {task['id']} "
                        f"completed by "
                        f"{task['agent']} "
                        f"using skill "
                        f"{skill_name} "
                        f"with tools "
                        f"[{tool_text}]"
                    )

                else:
                    messages.append(
                        f"Task {task['id']} "
                        f"completed by "
                        f"{task['agent']}"
                    )

                tracer.record(
                    event_type="task_completed",
                    workflow_id=workflow_id,
                    task_id=task["id"],
                    agent=task["agent"],
                    skill=skill_name,
                    latency_ms=task[
                        "latency_ms"
                    ],
                    success=True,
                    metadata={
                        "retry_count":
                            task[
                                "retry_count"
                            ],
                        "tools":
                            tool_names,
                    },
                )

            else:
                task[
                    "status"
                ] = (
                    "timeout"
                    if execution.get(
                        "timeout"
                    )
                    else "failed"
                )

                task[
                    "error"
                ] = execution.get(
                    "error"
                )

                error_message = (
                    f"Task {task['id']} "
                    f"{task['status']}: "
                    f"{task['error']}"
                )

                errors.append(
                    error_message
                )

                messages.append(
                    f"Task {task['id']} "
                    f"{task['status']}"
                )

                tracer.record(
                    event_type="task_failed",
                    workflow_id=workflow_id,
                    task_id=task["id"],
                    agent=task["agent"],
                    latency_ms=task[
                        "latency_ms"
                    ],
                    success=False,
                    metadata={
                        "retry_count":
                            task[
                                "retry_count"
                            ],
                        "timeout":
                            execution.get(
                                "timeout",
                                False,
                            ),
                        "error":
                            task.get(
                                "error"
                            ),
                    },
                )

    total_retries = sum(
        task.get(
            "retry_count",
            0,
        )
        for task
        in tasks
    )

    failed_tasks = [
        task
        for task
        in tasks
        if task.get(
            "status"
        ) in {
            "failed",
            "timeout",
        }
    ]

    remaining_pending_tasks = [
        task
        for task
        in tasks
        if task.get(
            "status"
        ) == "pending"
    ]

    if (
        failed_tasks
        or remaining_pending_tasks
        or errors
    ):
        status = "failed"
    else:
        status = (
            "agents_completed"
        )

    tracer.record(
        event_type="scheduler_completed",
        workflow_id=workflow_id,
        success=(
            status
            == "agents_completed"
        ),
        metadata={
            "status":
                status,
            "task_count":
                len(tasks),
            "total_retries":
                total_retries,
        },
    )

    return {
        "tasks":
            tasks,

        "task_results":
            task_results,

        "status":
            status,

        "messages":
            messages,

        "errors":
            errors,

        "total_retries":
            total_retries,
    }
