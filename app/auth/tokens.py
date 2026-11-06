import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import settings


REFRESH_TOKEN_PREFIX = "rt_"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_refresh_token() -> str:
    return REFRESH_TOKEN_PREFIX + secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expires_at(
    now: datetime | None = None,
) -> datetime:
    return (now or utcnow()) + timedelta(
        days=settings.refresh_token_ttl_days
    )


def refresh_token_max_age_seconds() -> int:
    return settings.refresh_token_ttl_days * 24 * 60 * 60
