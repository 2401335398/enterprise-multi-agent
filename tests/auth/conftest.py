from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Must be set before app.* imports. Authentication tests do not call an LLM,
# but importing app.main pulls in RAG/embedding modules.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-jwt-secret-" + "x" * 48,
)

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings  # noqa: E402
from app.db.session import get_db_session  # noqa: E402
from app.main import app  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    if not TEST_DATABASE_URL:
        return

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": TEST_DATABASE_URL,
        },
        check=True,
    )


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    monkeypatch.setattr(settings, "app_mode", "dev")
    monkeypatch.setattr(
        settings,
        "jwt_secret_key",
        "test-jwt-secret-" + "x" * 48,
    )
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "jwt_issuer", "test-issuer")
    monkeypatch.setattr(settings, "jwt_audience", "test-audience")
    monkeypatch.setattr(settings, "jwt_leeway_seconds", 0)
    monkeypatch.setattr(settings, "access_token_ttl_seconds", 900)
    monkeypatch.setattr(settings, "refresh_token_ttl_days", 7)

    monkeypatch.setattr(
        settings,
        "refresh_token_delivery",
        "body",
    )
    monkeypatch.setattr(
        settings,
        "refresh_token_cookie_name",
        "refresh_token",
    )
    monkeypatch.setattr(
        settings,
        "refresh_token_cookie_secure",
        False,
    )
    monkeypatch.setattr(
        settings,
        "refresh_token_cookie_samesite",
        "lax",
    )
    monkeypatch.setattr(
        settings,
        "refresh_token_reuse_grace_seconds",
        0,
    )

    monkeypatch.setattr(
        settings,
        "auth_allow_registration",
        None,
    )
    monkeypatch.setattr(settings, "password_min_length", 8)
    monkeypatch.setattr(settings, "password_max_length", 128)


@pytest_asyncio.fixture
async def engine():
    if not TEST_DATABASE_URL:
        pytest.skip(
            "TEST_DATABASE_URL is required for auth integration tests"
        )

    engine = create_async_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def clean_database(engine):
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE TABLE refresh_tokens, users "
                "RESTART IDENTITY CASCADE"
            )
        )

    yield


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def client(session_factory, clean_database):
    async def override_get_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = (
        override_get_db_session
    )

    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.pop(
            get_db_session,
            None,
        )
