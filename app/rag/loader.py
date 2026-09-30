from pathlib import Path
import hashlib
from app.rag.config import KNOWLEDGE_BASE_DIR


from docx import Document
from pypdf import PdfReader


def load_text_file(
    path: Path
) -> list[dict]:

    text = path.read_text(
        encoding="utf-8"
    )
    document_id = generate_document_id(path, KNOWLEDGE_BASE_DIR)
    checksum = calculate_checksum(path)

    return [
        {
            "text": text,
            "metadata": {
                "source": str(path),
                "file_name": path.name,
                "type": "txt",
                "document_id": document_id,
                "checksum": checksum,
            }
        }
    ]


def load_pdf_file(path: Path):
    document_id = generate_document_id(path, KNOWLEDGE_BASE_DIR)
    checksum = calculate_checksum(path)

    reader = PdfReader(path)
    documents = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if not text.strip():
            continue

        documents.append(
            {
                "text": text,
                "metadata": {
                    "document_id": document_id,
                    "checksum": checksum,
                    "source": str(path),
                    "file_name": path.name,
                    "type": "pdf",
                    "page": page_number,
                },
            }
        )

    return documents



def load_docx_file(
    path: Path
) -> list[dict]:

    doc = Document(
        str(path)
    )

    text = "\n".join(
        paragraph.text
        for paragraph
        in doc.paragraphs
        if paragraph.text.strip()
    )
    document_id = generate_document_id(path, KNOWLEDGE_BASE_DIR)
    checksum = calculate_checksum(path)

    return [
        {
            "text": text,

            "metadata": {
                "source":
                    str(path),

                "file_name":
                    path.name,

                "type":
                    "docx",
                "document_id": document_id,
                "checksum": checksum,
            }
        }
    ]


def load_document(
    path: Path
) -> list[dict]:

    suffix = path.suffix.lower()

    if suffix == ".txt":
        return load_text_file(
            path
        )

    if suffix == ".pdf":
        return load_pdf_file(
            path
        )

    if suffix == ".docx":
        return load_docx_file(
            path
        )

    return []


def load_directory(
    directory: Path
) -> list[dict]:

    documents = []

    for path in directory.rglob(
        "*"
    ):

        if not path.is_file():
            continue

        docs = load_document(
            path
        )

        documents.extend(
            docs
        )

    return documents

def generate_document_id(path: Path, knowledge_base_dir: Path) -> str:
    relative_path = path.resolve().relative_to(
        knowledge_base_dir.resolve()
    )

    normalized_path = relative_path.as_posix().lower()

    return hashlib.sha256(
        normalized_path.encode("utf-8")
    ).hexdigest()


def calculate_checksum(path: Path) -> str:
    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)

    return sha256.hexdigest()
