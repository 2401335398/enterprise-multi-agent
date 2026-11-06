from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from app.auth.exceptions import InvalidAccessToken
from app.auth.jwt import (
    create_access_token,
    decode_access_token,
)
from app.core.config import settings


@pytest.fixture(autouse=True)
def jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "x" * 64)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "jwt_issuer", "test-issuer")
    monkeypatch.setattr(settings, "jwt_audience", "test-audience")
    monkeypatch.setattr(settings, "jwt_leeway_seconds", 0)
    monkeypatch.setattr(settings, "access_token_ttl_seconds", 900)


def test_access_token_round_trip():
    token = create_access_token("user-id", token_version=3)

    payload = decode_access_token(token)

    assert payload["sub"] == "user-id"
    assert payload["typ"] == "access"
    assert payload["ver"] == 3
    assert payload["iss"] == "test-issuer"
    assert payload["aud"] == "test-audience"
    assert payload["jti"]


def test_expired_access_token_is_rejected():
    token = create_access_token(
        "user-id",
        token_version=0,
        expires_delta=timedelta(seconds=-5),
    )

    with pytest.raises(InvalidAccessToken):
        decode_access_token(token)


def test_tampered_access_token_is_rejected():
    token = create_access_token("user-id", token_version=0)

    with pytest.raises(InvalidAccessToken):
        decode_access_token(token + "x")


def test_wrong_type_is_rejected():
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {
            "sub": "user-id",
            "typ": "refresh",
            "jti": "jti",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "iss": "test-issuer",
            "aud": "test-audience",
            "ver": 0,
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(InvalidAccessToken):
        decode_access_token(token)


def test_wrong_audience_is_rejected():
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {
            "sub": "user-id",
            "typ": "access",
            "jti": "jti",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "iss": "test-issuer",
            "aud": "other-audience",
            "ver": 0,
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(InvalidAccessToken):
        decode_access_token(token)


def test_missing_required_claim_is_rejected():
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {
            "sub": "user-id",
            "typ": "access",
            "jti": "jti",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "iss": "test-issuer",
            "aud": "test-audience",
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(InvalidAccessToken):
        decode_access_token(token)
