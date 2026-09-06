from app.rag.chunker import (
    chunk_documents,
)

from app.rag.embeddings import (
    embedding_model,
)

from app.rag.loader import (
    load_directory,
)

from app.rag.config import (
    KNOWLEDGE_BASE_DIR,
)

from app.rag.vector_store import (
    vector_store,
)


def build_index():

    print(
        "[RAG] loading documents..."
    )

    documents = (
        load_directory(
            KNOWLEDGE_BASE_DIR
        )
    )

    print(
        f"[RAG] documents: "
        f"{len(documents)}"
    )

    chunks = (
        chunk_documents(
            documents
        )
    )

    print(
        f"[RAG] chunks: "
        f"{len(chunks)}"
    )

    if not chunks:

        print(
            "[RAG] no chunks found."
        )

        return

    texts = [
        chunk["text"]
        for chunk
        in chunks
    ]

    print(
        "[RAG] embedding..."
    )

    embeddings = (
        embedding_model
        .embed_documents(
            texts
        )
    )

    vector_store.add(

        ids=[
            chunk["id"]
            for chunk
            in chunks
        ],

        texts=texts,

        embeddings=embeddings,

        metadatas=[
            chunk["metadata"]
            for chunk
            in chunks
        ],
    )

    print(
        "[RAG] index completed."
    )
