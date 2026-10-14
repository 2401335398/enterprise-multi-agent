# RAG 检索评测

只测检索层本身：给一个问题，看正确的文档和页码有没有被召回。不经过 LLM 生成，
因此无需服务、无需 API key、秒级完成，可以直接进 CI。

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe evals/rag/evaluate_retrieval.py
```

## 数据集

[datasets/retrieval_cases.json](datasets/retrieval_cases.json) —— 8 条 NIST AI RMF
英文问题，覆盖 list / definition / explanation / specific_section / negative /
paraphrase / hard_negative / structure_sensitive 八种问题类型。

每条案例声明 `expected_document` + `relevant_pages`，用于判定命中。

## 指标

Hit@1 / Hit@3 / Hit@5 + MRR，分 vector / hybrid / hybrid_rerank 三档对比。
实现见 [app/evaluation/](../../app/evaluation/)。

当前基线见 [上级 README](../README.md#基线)。

## 前置条件

Chroma 索引必须已构建：

```bash
PYTHONPATH=. PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/build_rag_index.py
```

预期输出 `documents: 51` / `chunks: 153`。若 `data/chroma/` 为空，所有指标都会是 0，
这不是检索质量问题。

> 注意 `PYTHONPATH=.`：直接 `python scripts/build_rag_index.py` 会把 `scripts/`
> 而非仓库根目录放进 `sys.path`，导致 `ModuleNotFoundError: No module named 'app'`。

## 与端到端评测的关系

这里是**纯检索**指标。Agent 全链路的评测在 [../agent/](../agent/)，
其中离线专项 `CMP-RAG-03` 会复用本目录的 runner 记录同样的基线。
