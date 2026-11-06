import pytest

from app.auth.config import AuthConfigError, validate_auth_config
from app.core.config import settings


@pytest.fixture(autouse=True)
def safe_auth_settings(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "x" * 64)
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "access_token_ttl_seconds", 900)
    monkeypatch.setattr(settings, "refresh_token_ttl_days", 7)
    monkeypatch.setattr(settings, "jwt_leeway_seconds", 30)
    monkeypatch.setattr(
        settings,
        "refresh_token_reuse_grace_seconds",
        10,
    )
    monkeypatch.setattr(settings, "password_min_length", 8)
    monkeypatch.setattr(settings, "password_max_length", 128)
    monkeypatch.setattr(settings, "app_mode", "dev")


def test_valid_config_passes():
    validate_auth_config()


def test_short_secret_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "short")

    with pytest.raises(AuthConfigError):
        validate_auth_config()


def test_unsupported_algorithm_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "jwt_algorithm", "none")

    with pytest.raises(AuthConfigError):
        validate_auth_config()


def test_non_positive_access_ttl_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "access_token_ttl_seconds", 0)

    with pytest.raises(AuthConfigError):
        validate_auth_config()


def test_password_minimum_below_eight_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "password_min_length", 6)

    with pytest.raises(AuthConfigError):
        validate_auth_config()
