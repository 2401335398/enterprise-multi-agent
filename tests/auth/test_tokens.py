from datetime import timedelta

from app.auth.tokens import (
    REFRESH_TOKEN_PREFIX,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expires_at,
    utcnow,
)
from app.core.config import settings


def test_refresh_tokens_are_random_and_prefixed():
    tokens = {generate_refresh_token() for _ in range(100)}

    assert len(tokens) == 100
    assert all(token.startswith(REFRESH_TOKEN_PREFIX) for token in tokens)


def test_refresh_token_hash_is_stable_and_not_the_token():
    token = generate_refresh_token()

    first = hash_refresh_token(token)
    second = hash_refresh_token(token)

    assert first == second
    assert len(first) == 64
    assert first != token


def test_refresh_expiry_uses_configured_days():
    now = utcnow()
    expires_at = refresh_token_expires_at(now)

    assert expires_at == now + timedelta(
        days=settings.refresh_token_ttl_days
    )
