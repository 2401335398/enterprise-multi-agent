# app/observability/langfuse_integration.py

from __future__ import annotations

import os

from dotenv import load_dotenv


# ------------------------------------------------------------
# Load environment variables as early as possible.
# ------------------------------------------------------------

load_dotenv()


_LANGFUSE_CLIENT = None
_LANGFUSE_HANDLER = None


def get_langfuse_client():
    """
    Return a singleton Langfuse client.

    Returns None when:
    - Langfuse is not installed
    - credentials are not configured

    The client uses a larger timeout than the SDK default because
    some networks/proxies need more than ~5 seconds when exporting
    OpenTelemetry span batches.
    """

    global _LANGFUSE_CLIENT

    if _LANGFUSE_CLIENT is not None:
        return _LANGFUSE_CLIENT

    public_key = os.getenv(
        "LANGFUSE_PUBLIC_KEY"
    )

    secret_key = os.getenv(
        "LANGFUSE_SECRET_KEY"
    )

    base_url = (
        os.getenv(
            "LANGFUSE_BASE_URL"
        )
        or "https://cloud.langfuse.com"
    )

    if not (
        public_key
        and secret_key
    ):
        return None

    try:
        from langfuse import Langfuse

    except ImportError:
        return None

    _LANGFUSE_CLIENT = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,

        # Important:
        # SDK v4 trace exporter may otherwise time out
        # around 5 seconds on slower networks.
        timeout=30,

        environment=(
            os.getenv(
                "LANGFUSE_TRACING_ENVIRONMENT"
            )
            or "development"
        ),
    )

    return _LANGFUSE_CLIENT


def get_langfuse_handler():
    """
    Optional LangChain / LangGraph callback handler.

    Returns None when:
    - credentials are missing
    - Langfuse is not installed

    Uses the same Langfuse project configuration initialized above.
    """

    client = get_langfuse_client()

    if client is None:
        return None

    try:
        from langfuse.langchain import (
            CallbackHandler,
        )

    except ImportError:
        return None

    global _LANGFUSE_HANDLER

    if _LANGFUSE_HANDLER is None:
        _LANGFUSE_HANDLER = (
            CallbackHandler()
        )

    return _LANGFUSE_HANDLER


def flush_langfuse():
    """
    Force pending Langfuse spans to be exported.

    Mainly useful for tests and application shutdown.
    """

    client = get_langfuse_client()

    if client is None:
        return

    try:
        client.flush()

    except Exception as exc:
        print(
            "[LANGFUSE] flush failed:",
            exc,
        )
