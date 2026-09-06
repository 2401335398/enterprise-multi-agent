import json
from pathlib import Path

from app.evaluation.schema import (
    RAGEvalCase,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


EVAL_DATASET = (
    PROJECT_ROOT
    / "data"
    / "eval"
    / "rag_eval.json"
)


def load_rag_eval_dataset(
) -> list[RAGEvalCase]:

    with open(
        EVAL_DATASET,
        "r",
        encoding="utf-8"
    ) as f:

        raw = json.load(
            f
        )

    return [
        RAGEvalCase(
            **item
        )
        for item in raw
    ]
