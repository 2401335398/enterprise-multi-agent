from __future__ import annotations

import os


def get_langfuse_handler():
    """
    Optional Langfuse integration.

    Returns None when:
    - langfuse is not installed
    - credentials are not configured

    Therefore local development keeps working without Langfuse.
    """

    if not (
        os.getenv("LANGFUSE_PUBLIC_KEY")
        and os.getenv("LANGFUSE_SECRET_KEY")
    ):
        return None

    try:
        from langfuse.langchain import CallbackHandler
    except ImportError:
        return None

    return CallbackHandler()
