"""
Agent Evaluation —— 离线专项检查。

这些维度**无法端到端评测**，只能在这里测：

- 工具治理：agent 能触达的工具当前全是 ALLOW，allowed_agents 全为空，
  DENY 只是"未登记工具"的兜底，所以没有任何 agent→tool 组合会被拒。
  治理层因此只能在 evaluate() 这一层验证。
- Skill 路由：select_skill() 是纯函数，直接调比透过 LLM 规划间接观察精确得多。
- 检索质量与过滤器到底谁生效：document_search 从不传 filters，
  所以过滤行为只能离线验证。

全部无 LLM、无服务器、确定性，可进 CI。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from evals.agent.schema import CaseResult, CheckResult

# ============================================================
# 辅助
# ============================================================

def _ok(key: str, expected, actual, passed: bool, detail: str = "") -> CheckResult:
    return CheckResult(
        key=key,
        passed=passed,
        expected=expected,
        actual=actual,
        detail=detail,
    )


def _skill(agent: str, description: str, depends_on: list[str] | None = None) -> str:
    from app.skills.router import select_skill

    return select_skill(
        agent_name=agent,
        state={
            "current_task": {
                "description": description,
                "depends_on": depends_on or [],
            }
        },
    )


# ============================================================
# 1. 工具治理
# ============================================================

def check_tool_policy() -> list[CheckResult]:
    from app.tools.policy import tool_policy_engine

    checks: list[CheckResult] = []

    # --- ALLOW：agent 真正会调用的只读工具 ---
    allowed = tool_policy_engine.evaluate(
        "document_search", agent_name="knowledge"
    )
    checks.append(
        _ok(
            "policy_allow_document_search",
            "allow",
            allowed.action.value,
            allowed.action.value == "allow",
            f"reason={allowed.reason}",
        )
    )

    # --- REQUIRE_APPROVAL：写操作必须走人工审批 ---
    approval = tool_policy_engine.evaluate(
        "mcp.filesystem.write_file", agent_name="knowledge"
    )
    checks.append(
        _ok(
            "policy_require_approval_write",
            "require_approval",
            approval.action.value,
            approval.action.value == "require_approval",
            f"reason={approval.reason}",
        )
    )

    # --- DENY：未登记工具走默认拒绝 ---
    denied = tool_policy_engine.evaluate(
        "mcp.filesystem.delete_everything", agent_name="knowledge"
    )
    checks.append(
        _ok(
            "policy_deny_unregistered",
            "deny",
            denied.action.value,
            denied.action.value == "deny",
            f"reason={denied.reason}",
        )
    )

    # --- 特征化：当前没有任何 agent→tool 限制 ---
    # 这条不是在验"治理生效"，而是把现状固化下来，
    # 防止将来误以为治理层已经被端到端覆盖。
    from app.tools.policies import TOOL_POLICIES

    scoped = [p.tool_pattern for p in TOOL_POLICIES if p.allowed_agents]

    checks.append(
        _ok(
            "policy_no_agent_scoping_yet",
            "所有策略的 allowed_agents 均为空（现状）",
            scoped,
            scoped == [],
            "当前不存在 agent→tool 级限制；若开始使用 allowed_agents，"
            "请同步新增端到端治理案例" if scoped else "",
        )
    )

    return checks


# ============================================================
# 2. Skill 路由
# ============================================================

def check_skill_routing() -> list[CheckResult]:
    checks: list[CheckResult] = []

    cases = [
        (
            "skill_research_competitor_keyword",
            "research",
            "调研竞争对手的市场表现",
            [],
            "competitor_research",
        ),
        (
            "skill_research_default",
            "research",
            "调研制造业市场趋势",
            [],
            "web_research",
        ),
        (
            # 阈值优先于关键词：依赖 >= 2 直接 synthesis
            "skill_analysis_synthesis_by_dependency",
            "analysis",
            "汇总上游结果",
            ["T1", "T2"],
            "synthesis_analysis",
        ),
        (
            "skill_analysis_synthesis_by_keyword",
            "analysis",
            "给出下一步策略建议",
            [],
            "synthesis_analysis",
        ),
        (
            # 单依赖 + 无关键词 -> data_analysis
            "skill_analysis_data_default",
            "analysis",
            "计算这三个数的平均值",
            ["T1"],
            "data_analysis",
        ),
        (
            "skill_knowledge_always_document_search",
            "knowledge",
            "查询产品资料",
            [],
            "document_search",
        ),
    ]

    for key, agent, description, depends_on, expected in cases:
        try:
            actual = _skill(agent, description, depends_on)
            checks.append(
                _ok(
                    key,
                    expected,
                    actual,
                    actual == expected,
                    "" if actual == expected else f"路由到 {actual}，预期 {expected}",
                )
            )
        except Exception as exc:
            checks.append(
                _ok(key, expected, None, False, f"{type(exc).__name__}: {exc}")
            )

    return checks


# ============================================================
# 3. 引用编号地基
# ============================================================

def check_context_builder() -> list[CheckResult]:
    """
    [Source N] 必须严格等于结果列表位置。

    第五节断言引擎里的 require_citation / max_citation_index 依赖这个前提，
    所以这里先把它钉死。
    """

    from app.rag.context_builder import build_context

    results = [
        {"text": "第一段内容", "metadata": {"file_name": "a.txt"}},
        {"text": "第二段内容", "metadata": {"file_name": "b.txt", "page": 3}},
        {"text": "第三段内容", "metadata": {"file_name": "c.txt"}},
    ]

    context = build_context(results)

    checks = [
        _ok(
            "context_source_numbering_starts_at_1",
            "[Source 1]",
            context.strip()[:40],
            "[Source 1]" in context,
        ),
        _ok(
            "context_source_numbering_complete",
            "包含 [Source 1..3]",
            [n for n in (1, 2, 3) if f"[Source {n}]" in context],
            all(f"[Source {n}]" in context for n in (1, 2, 3)),
        ),
        _ok(
            "context_has_no_source_4",
            "不含 [Source 4]",
            "[Source 4]" in context,
            "[Source 4]" not in context,
            "编号越界会让引用断言失去意义",
        ),
    ]

    return checks


# ============================================================
# 4. 过滤器：Chroma 生效、BM25 不生效
# ============================================================

def check_retrieval_filters() -> list[CheckResult]:
    """
    把"过滤只对向量检索生效"这一现状固化。

    DocumentSearchTool 从不传 filters，所以这个缺陷目前不会被端到端路径触发；
    但一旦将来开始传 filters，BM25 静默忽略过滤会变成静默的召回污染。
    """

    checks: list[CheckResult] = []

    target = "product_update.txt"

    # --- Chroma 尊重 filters ---
    try:
        from app.rag.retriever import vector_retrieve

        hits = vector_retrieve("KnowledgeFlow", top_k=5, filters={"file_name": target})
        files = [hit["metadata"].get("file_name") for hit in hits]

        checks.append(
            _ok(
                "filter_chroma_honored",
                f"全部来自 {target}",
                files,
                bool(files) and all(name == target for name in files),
                "" if files and all(n == target for n in files)
                else "向量检索没有正确应用 file_name 过滤",
            )
        )
    except Exception as exc:
        checks.append(
            _ok("filter_chroma_honored", target, None, False,
                f"{type(exc).__name__}: {exc}")
        )

    # --- BM25 忽略 filters（特征化既有缺陷）---
    try:
        from app.rag.bm25 import bm25_retriever

        unfiltered = bm25_retriever.search("KnowledgeFlow", top_k=10)
        filtered = bm25_retriever.search(
            "KnowledgeFlow", top_k=10, filters={"file_name": target}
        )

        same = [item["id"] for item in unfiltered] == [item["id"] for item in filtered]

        files = sorted({
            item["metadata"].get("file_name") for item in filtered
        })

        checks.append(
            _ok(
                "filter_bm25_ignored_known_gap",
                "带不带 filters 结果相同（已知缺陷）",
                files,
                same,
                "" if same
                else "BM25 开始尊重 filters 了——这是行为变更，请更新本检查与文档",
            )
        )
    except Exception as exc:
        checks.append(
            _ok("filter_bm25_ignored_known_gap", None, None, False,
                f"{type(exc).__name__}: {exc}")
        )

    return checks


# ============================================================
# 5. 检索质量基线
# ============================================================

def check_retrieval_baseline() -> list[CheckResult]:
    """
    复用既有的 app/evaluation，跑 vector / hybrid / hybrid_rerank 三档基线，
    把数值记录下来供趋势对比。
    """

    checks: list[CheckResult] = []

    try:
        from app.evaluation.metrics import summarize_results
        from app.evaluation.runner import run_retrieval_evaluation

        summary = summarize_results(run_retrieval_evaluation())
    except Exception as exc:
        return [
            _ok("retrieval_baseline_available", "可运行", None, False,
                f"{type(exc).__name__}: {exc}")
        ]

    for strategy in ("vector", "hybrid", "hybrid_rerank"):
        metrics = summary.get(strategy)

        if not metrics:
            checks.append(
                _ok(f"retrieval_{strategy}_present", "有结果", None, False, "无该检索器结果")
            )
            continue

        checks.append(
            _ok(
                f"retrieval_{strategy}_baseline",
                "hit@3 > 0",
                {
                    "hit@1": round(metrics.get("hit@1", 0), 3),
                    "hit@3": round(metrics.get("hit@3", 0), 3),
                    "hit@5": round(metrics.get("hit@5", 0), 3),
                    "mrr": round(metrics.get("mrr", 0), 3),
                },
                metrics.get("hit@3", 0) > 0,
                "数值仅供基线记录与趋势对比",
            )
        )

    return checks


# ============================================================
# 注册表
# ============================================================

@dataclass
class ComponentCase:
    id: str
    name: str
    dimension: str
    fn: Callable[[], list[CheckResult]]


COMPONENT_CASES: list[ComponentCase] = [
    ComponentCase(
        id="CMP-POLICY-01",
        name="工具治理：ALLOW / REQUIRE_APPROVAL / DENY",
        dimension="tool_governance",
        fn=check_tool_policy,
    ),
    ComponentCase(
        id="CMP-SKILL-01",
        name="Skill 路由：确定性规则",
        dimension="skill_routing",
        fn=check_skill_routing,
    ),
    ComponentCase(
        id="CMP-RAG-01",
        name="引用编号地基：build_context",
        dimension="rag_internals",
        fn=check_context_builder,
    ),
    ComponentCase(
        id="CMP-RAG-02",
        name="过滤器：Chroma 生效 / BM25 忽略",
        dimension="rag_internals",
        fn=check_retrieval_filters,
    ),
    ComponentCase(
        id="CMP-RAG-03",
        name="检索质量基线",
        dimension="rag_internals",
        fn=check_retrieval_baseline,
    ),
]


def run_component_cases() -> list[CaseResult]:
    """执行全部离线专项检查，单个失败不影响其余。"""

    from evals.agent.schema import StepResult

    results: list[CaseResult] = []

    for case in COMPONENT_CASES:
        started = time.perf_counter()

        try:
            checks = case.fn()
            error = None
        except Exception as exc:
            checks = [
                CheckResult(
                    key=f"{case.dimension}_crashed",
                    passed=False,
                    expected="正常执行",
                    actual=None,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            ]
            error = f"{type(exc).__name__}: {exc}"

        failed_keys = [c.key for c in checks if not c.passed]

        results.append(
            CaseResult(
                id=case.id,
                name=case.name,
                dimension=case.dimension,
                tags=["component", "offline"],
                kind="component",
                elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                passed=not failed_keys,
                steps=[
                    StepResult(
                        step=1,
                        message="(offline)",
                        failed=bool(failed_keys),
                        checks=checks,
                    )
                ],
                failed_keys=failed_keys,
                error=error,
            )
        )

    return results
