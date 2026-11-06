import pytest

from app.auth.passwords import (
    dummy_password_hash,
    hash_password,
    validate_password_policy,
    verify_and_update_password,
    verify_password,
)
from app.core.config import settings


def test_hash_is_not_plaintext_and_verifies():
    hashed = hash_password("correct-horse-battery-staple")

    assert hashed != "correct-horse-battery-staple"
    assert hashed.startswith("$argon2")
    assert verify_password(
        "correct-horse-battery-staple",
        hashed,
    )


def test_wrong_password_is_rejected():
    hashed = hash_password("correct-horse-battery-staple")

    assert not verify_password("wrong-password", hashed)


def test_verify_and_update_returns_new_hash_when_needed():
    hashed = hash_password("correct-horse-battery-staple")

    valid, new_hash = verify_and_update_password(
        "correct-horse-battery-staple",
        hashed,
    )

    assert valid is True
    assert new_hash is None


def test_malformed_hash_does_not_raise():
    assert not verify_password("anything", "not-a-valid-hash")
    assert verify_and_update_password(
        "anything",
        "not-a-valid-hash",
    ) == (False, None)


def test_dummy_hash_is_stable_and_never_matches():
    first = dummy_password_hash()
    second = dummy_password_hash()

    assert first == second
    assert not verify_password("some-other-password", first)


def test_valid_password_passes_policy():
    validate_password_policy("correct-horse-battery-staple")


@pytest.mark.parametrize(
    "password",
    [
        "",
        "short",
        "        ",
        "abc\x00defgh",
    ],
)
def test_invalid_passwords_are_rejected(password):
    with pytest.raises(ValueError):
        validate_password_policy(password)


def test_password_longer_than_maximum_is_rejected():
    password = "a" * (settings.password_max_length + 1)

    with pytest.raises(ValueError):
        validate_password_policy(password)
