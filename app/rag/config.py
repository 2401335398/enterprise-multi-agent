from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


KNOWLEDGE_BASE_DIR = (
    PROJECT_ROOT
    / "knowledge_base"
)


CHROMA_DIR = (
    PROJECT_ROOT
    / "data"
    / "chroma"
)


COLLECTION_NAME = (
    "enterprise_knowledge"
)


EMBEDDING_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


CHUNK_SIZE = 500

CHUNK_OVERLAP = 100


TOP_K = 5

RERANKER_MODEL = (
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

RERANK_CANDIDATES = 10

FINAL_TOP_K = 5
