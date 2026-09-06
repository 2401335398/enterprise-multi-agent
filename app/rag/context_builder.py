def build_context(
    results: list[dict]
) -> str:

    blocks = []

    for index, result in enumerate(
        results,
        start=1
    ):

        metadata = result.get(
            "metadata",
            {}
        )

        file_name = (
            metadata.get(
                "file_name",
                "unknown"
            )
        )

        page = metadata.get(
            "page"
        )

        chunk_id = metadata.get(
            "chunk_id"
        )

        source_lines = [
            f"[Source {index}]",
            f"file: {file_name}",
        ]

        if page is not None:

            source_lines.append(
                f"page: {page}"
            )

        if chunk_id:

            source_lines.append(
                f"chunk_id: {chunk_id}"
            )

        source_lines.append(
            ""
        )

        source_lines.append(
            result["text"]
        )

        blocks.append(
            "\n".join(
                source_lines
            )
        )

    return (
        "\n\n"
        "--------------------"
        "\n\n"
    ).join(
        blocks
    )
