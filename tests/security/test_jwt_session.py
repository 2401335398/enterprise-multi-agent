import uuid

from app.security.auth import Principal
from app.security.session import (
    owns_session,
    resolve_session_id,
)


USER_ID = "8d3a4f8e-6f1d-4f6c-9f0e-6a1f5b2c7d10"


def test_dev_jwt_principal_is_namespaced(dev_mode):
    principal = Principal(
        name=f"user:{USER_ID}",
        user_id=USER_ID,
        auth_method="jwt",
    )

    session_id = resolve_session_id(principal, "shared")

    assert session_id == f"user:{USER_ID}:shared"
    assert owns_session(principal, session_id)

    # Round-tripping the returned id must not add another prefix.
    assert (
        resolve_session_id(principal, session_id)
        == session_id
    )


def test_dev_local_principal_keeps_old_behaviour(dev_mode):
    principal = Principal(
        name="local",
        auth_method="local",
    )

    assert resolve_session_id(principal, "shared") == "shared"

    generated = resolve_session_id(principal, None)
    uuid.UUID(generated)
    assert ":" not in generated


def test_demo_api_key_principal_is_namespaced(demo_mode):
    principal = Principal(
        name="alice",
        auth_method="api_key",
    )

    assert (
        resolve_session_id(principal, "shared")
        == "alice:shared"
    )


def test_jwt_and_api_key_namespaces_do_not_collide(demo_mode):
    api_key_principal = Principal(
        name="alice",
        auth_method="api_key",
    )
    jwt_principal = Principal(
        name=f"user:{USER_ID}",
        user_id=USER_ID,
        auth_method="jwt",
    )

    api_key_session = resolve_session_id(
        api_key_principal,
        "shared",
    )
    jwt_session = resolve_session_id(
        jwt_principal,
        "shared",
    )

    assert api_key_session != jwt_session
    assert not owns_session(
        api_key_principal,
        jwt_session,
    )
    assert not owns_session(
        jwt_principal,
        api_key_session,
    )
