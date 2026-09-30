from app.rag.chunker import chunk_documents


def test_chunk_id_is_stable_when_other_document_is_added():
    document = {
        "text": "ABCDEFGHIJ",
        "metadata": {
            "document_id": "doc_B",
            "file_name": "B.txt",
        },
    }

    extra_document = {
        "text": "XXXXXXXXXX",
        "metadata": {
            "document_id": "doc_A",
            "file_name": "A.txt",
        },
    }

    chunks_without_extra = chunk_documents([document])
    chunks_with_extra = chunk_documents(
        [extra_document, document]
    )

    b_id_without_extra = chunks_without_extra[0]["id"]
    b_id_with_extra = chunks_with_extra[1]["id"]

    assert b_id_without_extra == b_id_with_extra


def test_chunk_ids_are_unique_across_pdf_pages():
    page_1 = {
        "text": "same text",
        "metadata": {
            "document_id": "doc_pdf",
            "file_name": "test.pdf",
            "page": 1,
        },
    }

    page_2 = {
        "text": "same text",
        "metadata": {
            "document_id": "doc_pdf",
            "file_name": "test.pdf",
            "page": 2,
        },
    }

    chunks = chunk_documents([page_1, page_2])

    assert chunks[0]["metadata"]["chunk_index"] == 0
    assert chunks[1]["metadata"]["chunk_index"] == 0

    assert chunks[0]["id"] != chunks[1]["id"]
