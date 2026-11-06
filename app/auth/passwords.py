from functools import lru_cache

from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

from app.core.config import settings


password_hasher = PasswordHash.recommended()


def validate_password_policy(password: str) -> None:
    """Raise ValueError when the password does not satisfy the policy."""

    if not password or not password.strip():
        raise ValueError("Password must not be empty.")

    if len(password) < settings.password_min_length:
        raise ValueError(
            "Password must be at least "
            f"{settings.password_min_length} characters long."
        )

    if len(password) > settings.password_max_length:
        raise ValueError(
            "Password must be at most "
            f"{settings.password_max_length} characters long."
        )

    if "\x00" in password:
        raise ValueError("Password must not contain null bytes.")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except PwdlibError:
        # A malformed hash in the database must not turn into a 500.
        return False


def verify_and_update_password(
    password: str,
    password_hash: str,
) -> tuple[bool, str | None]:
    """
    Verify a password and return a new hash when the hasher's parameters
    have changed. The caller is responsible for persisting the new hash.
    """

    try:
        return password_hasher.verify_and_update(
            password,
            password_hash,
        )
    except PwdlibError:
        return False, None


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    """
    Used when the email does not exist so that unknown-email logins perform
    the same expensive hash verification as known-email logins.
    """

    return hash_password("not-a-real-password")
