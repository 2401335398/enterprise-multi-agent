from pathlib import Path

from app.rag.loader import (
    calculate_checksum,
    generate_document_id,
)


def test_document_id_is_stable_when_content_changes(tmp_path: Path):
    knowledge_base = tmp_path / "knowledge_base"
    knowledge_base.mkdir()

    document = knowledge_base / "example.txt"
    document.write_text("version 1", encoding="utf-8")

    document_id_before = generate_document_id(
        document,
        knowledge_base,
    )

    document.write_text("version 2", encoding="utf-8")

    document_id_after = generate_document_id(
        document,
        knowledge_base,
    )

    assert document_id_before == document_id_after


def test_checksum_changes_when_content_changes(tmp_path: Path):
    document = tmp_path / "example.txt"
    document.write_text("version 1", encoding="utf-8")

    checksum_before = calculate_checksum(document)

    document.write_text("version 2", encoding="utf-8")

    checksum_after = calculate_checksum(document)

    assert checksum_before != checksum_after


def test_document_id_changes_when_path_changes(tmp_path: Path):
    knowledge_base = tmp_path / "knowledge_base"
    knowledge_base.mkdir()

    first = knowledge_base / "first.txt"
    second = knowledge_base / "second.txt"

    first.write_text("same content", encoding="utf-8")
    second.write_text("same content", encoding="utf-8")

    first_id = generate_document_id(first, knowledge_base)
    second_id = generate_document_id(second, knowledge_base)

    assert first_id != second_id
