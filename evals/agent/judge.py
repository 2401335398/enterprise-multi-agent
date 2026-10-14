"""
Agent Evaluation —— LLM-as-Judge。

定位：确定性断言管"结构对不对"，judge 管"答案好不好"。两者分别计分，
不混进同一个 pass；默认 judge 也不参与退出码，只有 --judge-strict 才计入。

关键设计：judge 必须拿到**证据**才能判断答案是否编造。证据从被评测任务的
tool_results 里取（knowledge 任务的 RAG context、research 任务的搜索结果），
由案例的 judge.evidence_from 指定。

计量隔离：judge 用自己的 ChatOpenAI 实例，不走 app 的 tracked_llm_invoke，
因此不会污染被测系统的 token / cost 计数。judge 成本单独累计。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from app.core.config import settings
from app.observability.cost import estimate_cost

# 改动 prompt 必须同时改版本号：它会写进结果 JSON，用于跨版本比较
JUDGE_PROMPT_VERSION = "v1"

DIMENSION_DESCRIPTIONS = {
    "groundedness":
        "答案里的每条结论是否都能在证据中找到支撑。"
        "出现证据中没有的具体数字、日期、产品名、结论 = 编造，打低分。",
    "citation":
        "[Source N] 引用是否存在、编号是否真实对应证据条目、有没有张冠李戴。"
        "完全没有引用打低分。",
    "evidence_boundary":
        "证据不足以回答时，是否明确说明而不是自行补全。"
        "证据充足时不应无端推脱，也要扣分。",
    "completeness":
        "是否回答了用户真正问的问题，有没有答非所问、避重就轻。",
    "synthesis_quality":
        "多来源结果是否真的被综合对比。"
        "只是把几段原文拼在一起而没有比较/归纳，打低分。",
}

JUDGE_SYSTEM_PROMPT = """你是企业级 AI 系统的独立评测员。

你会收到：用户的原始问题、系统给出的答案、以及系统当时检索到的证据。

你的任务是严格按证据评判答案质量。要求：

1. 只依据给出的证据判断，不要用自己的外部知识替系统"补答案"。
2. 如果答案里出现了证据中不存在的事实，必须指出并扣分。
3. 证据不足以回答时，系统明确说明"证据不足"是**正确**行为，应给高分。
4. 逐维度独立打分，不要因为一个维度差就把所有维度都打低。
5. 必须只输出一个 JSON 对象，不要输出 Markdown，不要输出 ```json，不要任何解释。
"""

JUDGE_USER_TEMPLATE = """用户问题：

{query}


系统答案：

{answer}


系统检索到的证据：

{evidence}


请按以下维度各打 1-5 分（5 = 最好）：

{dimensions}


严格输出以下 JSON 格式：

{{
  "scores": {{ "维度名": 整数 }},
  "reasons": {{ "维度名": "一句话理由" }},
  "flags": {{
    "fabricated_facts": true/false,
    "citation_mismatch": true/false,
    "false_refusal": true/false
  }}
}}
"""


def _extract_json(text: str) -> dict:
    """从 LLM 输出里尽量抠出 JSON 对象。"""

    if not text:
        raise ValueError("judge 返回空内容")

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(f"judge 输出中没有 JSON 对象：{text[:300]!r}")

    return json.loads(text[start:end + 1])


def extract_evidence(response: dict, spec: str | None) -> str:
    """
    按案例配置取证据文本。

    spec 形如 "task_with_skill:document_search"。
    取不到时返回占位说明，而不是空字符串——让 judge 知道"没有证据"
    本身也是一条信息（此时正确答案应该是拒答）。
    """

    if not spec:
        return "（本次评测未配置证据来源）"

    if not spec.startswith("task_with_skill:"):
        return f"（不认识的 evidence_from 配置：{spec}）"

    skill_name = spec.split(":", 1)[1]

    blocks: list[str] = []

    for task in (response.get("tasks") or []):
        if task.get("skill") != skill_name:
            continue

        for result in (task.get("tool_results") or []):
            if not isinstance(result, dict):
                continue

            payload = result.get("result")

            if not isinstance(payload, dict):
                continue

            # document_search -> RAGService.search 输出
            context = payload.get("context")
            if isinstance(context, str) and context.strip():
                blocks.append(context)
                continue

            # search / browser -> 原始工具输出
            if payload:
                blocks.append(json.dumps(payload, ensure_ascii=False)[:4000])

    if not blocks:
        return "（本次运行没有检索到任何证据）"

    return "\n\n========\n\n".join(blocks)


class Judge:
    """LLM-as-Judge，懒加载底层模型。"""

    def __init__(self, model: str | None = None):
        self.model_name = model or getattr(settings, "llm_model", "")
        self._llm = None
        self.total_cost_usd = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.calls = 0
        self.errors = 0

    # --------------------------------------------------------

    def _get_llm(self):
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            judge_model = os.getenv("JUDGE_MODEL") or settings.llm_model

            self.model_name = judge_model

            self._llm = ChatOpenAI(
                model=judge_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0,
            )

        return self._llm

    # --------------------------------------------------------

    def judge(
        self,
        *,
        query: str,
        response: dict,
        dimensions: list[str],
        evidence_from: str | None,
    ) -> dict[str, Any]:
        """
        返回 {scores, reasons, flags, cost_usd, model, prompt_version}。
        任一环节失败都不抛异常，而是标记 judge_error，避免评测整体崩掉。
        """

        dims = dimensions or list(DIMENSION_DESCRIPTIONS)

        asked = {
            dim: DIMENSION_DESCRIPTIONS.get(dim, dim)
            for dim in dims
        }

        dimensions_text = "\n".join(
            f"- {name}: {desc}"
            for name, desc in asked.items()
        )

        answer = str(response.get("answer") or "")

        prompt = JUDGE_USER_TEMPLATE.format(
            query=query,
            answer=answer,
            evidence=extract_evidence(response, evidence_from),
            dimensions=dimensions_text,
        )

        self.calls += 1

        try:
            llm = self._get_llm()

            # 同步调用：CLI 本身是串行的，同步调用可以避免
            # 每次 judge 都新建 event loop 把 httpx AsyncClient 绑死在已关闭的循环上
            result = llm.invoke(
                [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
            )

            self._account_cost(result)

            payload = _extract_json(str(result.content))

        except Exception as exc:
            self.errors += 1

            return {
                "scores": {},
                "reasons": {},
                "flags": {},
                "cost_usd": 0.0,
                "model": self.model_name,
                "prompt_version": JUDGE_PROMPT_VERSION,
                "judge_error": f"{type(exc).__name__}: {exc}",
            }

        scores = payload.get("scores") or {}
        reasons = payload.get("reasons") or {}

        # 只保留问过的维度，且强制转 int（LLM 有时给字符串）
        clean_scores: dict[str, int] = {}

        for dim in asked:
            value = scores.get(dim)

            if value is None:
                continue

            try:
                clean_scores[dim] = int(value)
            except (TypeError, ValueError):
                continue

        return {
            "scores": clean_scores,
            "reasons": {
                dim: str(reasons.get(dim, ""))
                for dim in asked
            },
            "flags": payload.get("flags") or {},
            "cost_usd": 0.0,          # 单次成本在 _account_cost 里累计
            "model": self.model_name,
            "prompt_version": JUDGE_PROMPT_VERSION,
        }

    # --------------------------------------------------------

    def _account_cost(self, result: Any) -> None:
        usage = getattr(result, "usage_metadata", None)

        if not usage:
            return

        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        self.total_cost_usd += estimate_cost(input_tokens, output_tokens)

    # --------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "prompt_version": JUDGE_PROMPT_VERSION,
            "calls": self.calls,
            "errors": self.errors,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd": round(self.total_cost_usd, 8),
        }
