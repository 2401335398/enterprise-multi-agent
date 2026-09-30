from app.rag.config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
import hashlib

def generate_chunk_id(
    document_id: str,
    chunk_index: int,
    page: int | None = None,
) -> str:
    identity = (
        f"{document_id}:"
        f"{page if page is not None else 'none'}:"
        f"{chunk_index}"
    )

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()



def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:

    text = text.strip()

    if not text:
        return []

    chunks = []

    start = 0

    text_length = len(
        text
    )

    while start < text_length:

        end = min(
            start + chunk_size,
            text_length
        )

        chunk = text[
            start:end
        ]

        chunks.append(
            chunk
        )

        if end >= text_length:
            break

        start = (
            end - overlap
        )

    return chunks


def chunk_documents(
    documents: list[dict]
) -> list[dict]:

    chunks = []

    # chunk_counter = 0

    for document in documents:

        text_chunks = (
            split_text(
                document["text"]
            )
        )

        for index, text in enumerate(
            text_chunks
        ):

            metadata = dict(
                document["metadata"]
            )

            metadata[
                "chunk_index"
            ] = index

            metadata["chunk_id"] = generate_chunk_id(
                document_id=metadata["document_id"],
                page=metadata.get("page"),
                chunk_index=index,
            )

            chunks.append(
                {
                    "id":
                        metadata[
                            "chunk_id"
                        ],

                    "text":
                        text,

                    "metadata":
                        metadata,
                }
            )

            # chunk_counter += 1

    return chunks
