from pydantic import BaseModel, Field


class RAGEvalCase(BaseModel):

    id: str

    query: str

    expected_sources: list[str] = Field(
        default_factory=list
    )

    expected_keywords: list[str] = Field(
        default_factory=list
    )


class RetrievalEvalResult(BaseModel):

    case_id: str

    query: str

    retriever: str

    hit_at_1: bool

    hit_at_3: bool

    hit_at_5: bool

    reciprocal_rank: float

    retrieved_sources: list[str]
