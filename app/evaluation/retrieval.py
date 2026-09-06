from app.evaluation.schema import (
    RAGEvalCase,
    RetrievalEvalResult,
)


def extract_source(
    result: dict
) -> str:

    metadata = result.get(
        "metadata",
        {}
    )

    return (
        metadata.get(
            "file_name",
            ""
        )
    )


def is_relevant(
    result: dict,
    case: RAGEvalCase
) -> bool:

    source = extract_source(
        result
    )

    text = (
        result.get(
            "text",
            ""
        )
        .lower()
    )

    # -------------------------
    # Source Match
    # -------------------------

    source_match = (
        not case.expected_sources
        or source
        in case.expected_sources
    )

    # -------------------------
    # Keyword Match
    # -------------------------

    keyword_match = (
        not case.expected_keywords
        or any(
            keyword.lower()
            in text
            for keyword
            in case.expected_keywords
        )
    )

    return (
        source_match
        and keyword_match
    )


def evaluate_case(
    case: RAGEvalCase,
    results: list[dict],
    retriever_name: str,
) -> RetrievalEvalResult:

    relevant_rank = None

    retrieved_sources = []

    for rank, result in enumerate(
        results,
        start=1
    ):

        source = extract_source(
            result
        )

        retrieved_sources.append(
            source
        )

        if (
            relevant_rank is None
            and is_relevant(
                result,
                case
            )
        ):

            relevant_rank = rank

    reciprocal_rank = (
        1.0 / relevant_rank
        if relevant_rank
        else 0.0
    )

    return RetrievalEvalResult(

        case_id=
            case.id,

        query=
            case.query,

        retriever=
            retriever_name,

        hit_at_1=(
            relevant_rank is not None
            and relevant_rank <= 1
        ),

        hit_at_3=(
            relevant_rank is not None
            and relevant_rank <= 3
        ),

        hit_at_5=(
            relevant_rank is not None
            and relevant_rank <= 5
        ),

        reciprocal_rank=
            reciprocal_rank,

        retrieved_sources=
            retrieved_sources,
    )
