from typing import Any

from pydantic import BaseModel, Field


class RetrievalFilter(BaseModel):

    filters: dict[
        str,
        Any
    ] = Field(
        default_factory=dict
    )


class RetrievalQuery(BaseModel):

    original_query: str

    rewritten_query: str

    filters: RetrievalFilter = (
        RetrievalFilter()
    )
