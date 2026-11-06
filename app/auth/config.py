import logging

from app.core.config import settings


logger = logging.getLogger(__name__)

ALLOWED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}


class AuthConfigError(RuntimeError):
    """Authentication configuration is unsafe or incomplete."""


def validate_auth_config() -> None:
    """
    Fail fast at startup instead of silently running with an insecure or
    broken authentication configuration.
    """

    if len(settings.jwt_secret_key.encode("utf-8")) < 32:
        raise AuthConfigError(
            "JWT_SECRET_KEY is missing or too short. "
            "Set it to a random string of at least 32 bytes "
            "(64+ recommended). Generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )

    if settings.jwt_algorithm not in ALLOWED_JWT_ALGORITHMS:
        raise AuthConfigError(
            "JWT_ALGORITHM must be one of "
            f"{sorted(ALLOWED_JWT_ALGORITHMS)}."
        )

    if settings.access_token_ttl_seconds <= 0:
        raise AuthConfigError(
            "ACCESS_TOKEN_TTL_SECONDS must be greater than zero."
        )

    if settings.refresh_token_ttl_days <= 0:
        raise AuthConfigError(
            "REFRESH_TOKEN_TTL_DAYS must be greater than zero."
        )

    if settings.jwt_leeway_seconds < 0:
        raise AuthConfigError(
            "JWT_LEEWAY_SECONDS must not be negative."
        )

    if settings.refresh_token_reuse_grace_seconds < 0:
        raise AuthConfigError(
            "REFRESH_TOKEN_REUSE_GRACE_SECONDS must not be negative."
        )

    if settings.password_min_length < 8:
        raise AuthConfigError(
            "PASSWORD_MIN_LENGTH must be at least 8."
        )

    if settings.password_max_length < settings.password_min_length:
        raise AuthConfigError(
            "PASSWORD_MAX_LENGTH must be greater than or equal to "
            "PASSWORD_MIN_LENGTH."
        )

    if settings.is_demo and not settings.refresh_token_cookie_secure:
        logger.warning(
            "APP_MODE=demo but REFRESH_TOKEN_COOKIE_SECURE=false. "
            "Use HTTPS and set it to true in public deployments."
        )

    if settings.is_demo and settings.refresh_token_delivery == "body":
        logger.warning(
            "APP_MODE=demo but REFRESH_TOKEN_DELIVERY=body. "
            "Browser clients should use the HttpOnly cookie mode."
        )
