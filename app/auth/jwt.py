from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt as pyjwt
from jwt import InvalidTokenError

from app.auth.exceptions import InvalidAccessToken
from app.core.config import settings


def create_access_token(
    user_id: str,
    token_version: int,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(seconds=settings.access_token_ttl_seconds)
    )

    payload = {
        "sub": str(user_id),
        "typ": "access",
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "ver": int(token_version),
    }

    return pyjwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    try:
        payload = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=settings.jwt_leeway_seconds,
            options={
                "require": [
                    "exp",
                    "iat",
                    "sub",
                    "typ",
                    "jti",
                    "ver",
                ]
            },
        )
    except InvalidTokenError as exc:
        raise InvalidAccessToken(
            "Invalid or expired access token."
        ) from exc

    if payload.get("typ") != "access":
        raise InvalidAccessToken("Invalid access token type.")

    return payload
