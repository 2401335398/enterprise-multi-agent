from pathlib import Path

from docx import Document
from pypdf import PdfReader


def load_text_file(
    path: Path
) -> list[dict]:

    text = path.read_text(
        encoding="utf-8"
    )

    return [
        {
            "text": text,
            "metadata": {
                "source": str(path),
                "file_name": path.name,
                "type": "txt",
            }
        }
    ]


def load_pdf_file(
    path: Path
) -> list[dict]:

    reader = PdfReader(
        str(path)
    )

    documents = []

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        text = (
            page.extract_text()
            or ""
        )

        if not text.strip():
            continue

        documents.append(
            {
                "text": text,

                "metadata": {
                    "source":
                        str(path),

                    "file_name":
                        path.name,

                    "type":
                        "pdf",

                    "page":
                        page_number,
                }
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
