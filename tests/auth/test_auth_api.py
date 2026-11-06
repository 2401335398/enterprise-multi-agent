from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.auth.jwt import create_access_token
from app.core.config import settings
from app.db.models import UserModel


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason=(
            "TEST_DATABASE_URL is required for auth "
            "integration tests"
        ),
    ),
]


PASSWORD = "correct-horse-battery-staple"


async def register_user(
    client,
    *,
    email: str = "alice@example.com",
    password: str = PASSWORD,
    display_name: str | None = None,
):
    payload = {
        "email": email,
        "password": password,
    }

    if display_name is not None:
        payload["display_name"] = display_name

    return await client.post(
        "/api/auth/register",
        json=payload,
    )


async def login_user(
    client,
    *,
    email: str = "alice@example.com",
    password: str = PASSWORD,
):
    return await client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )


async def test_register_login_me_flow(client):
    registered = await register_user(
        client,
        email="Alice@Example.COM",
    )

    assert registered.status_code == 201

    user = registered.json()
    assert user["email"] == "alice@example.com"
    assert user["display_name"] == "alice"
    assert user["is_active"] is True
    assert "password" not in user
    assert "password_hash" not in user

    logged_in = await login_user(client)

    assert logged_in.status_code == 200

    tokens = logged_in.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 900
    assert tokens["access_token"]
    assert tokens["refresh_token"].startswith("rt_")
    assert tokens["user"]["email"] == "alice@example.com"
    assert tokens["user"]["last_login_at"] is not None

    me = await client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        },
    )

    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"

    anonymous = await client.get("/api/auth/me")
    assert anonymous.status_code == 401


async def test_duplicate_email_is_case_insensitive(client):
    assert (
        await register_user(
            client,
            email="Alice@Example.COM",
        )
    ).status_code == 201

    duplicate = await register_user(
        client,
        email="alice@example.com",
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Email already registered."


async def test_register_validation_errors(client):
    invalid_email = await client.post(
        "/api/auth/register",
        json={
            "email": "not-an-email",
            "password": PASSWORD,
        },
    )
    assert invalid_email.status_code == 422

    weak_password = await register_user(
        client,
        password="short",
    )
    assert weak_password.status_code == 422


async def test_login_failure_is_generic(client):
    await register_user(client)

    wrong_password = await login_user(
        client,
        password="wrong-but-long-enough",
    )
    unknown_email = await login_user(
        client,
        email="nobody@example.com",
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert (
        wrong_password.json()["detail"]
        == unknown_email.json()["detail"]
    )


async def test_inactive_user_cannot_login(
    client,
    session_factory,
):
    await register_user(client)

    async with session_factory() as session:
        await session.execute(
            update(UserModel)
            .where(UserModel.email == "alice@example.com")
            .values(is_active=False)
        )
        await session.commit()

    response = await login_user(client)

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is disabled."


async def test_refresh_rotation_and_reuse_detection(client):
    logged_in = await login_user(client)
    assert logged_in.status_code == 200

    first = logged_in.json()

    rotated = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert rotated.status_code == 200

    second = rotated.json()
    assert second["refresh_token"] != first["refresh_token"]

    # Reusing the old token is treated as theft.
    reuse = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert reuse.status_code == 401

    # The whole family is revoked, including the successor.
    successor = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": second["refresh_token"]},
    )
    assert successor.status_code == 401

    # token_version was bumped, so the access token is dead too.
    me = await client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {second['access_token']}"
        },
    )
    assert me.status_code == 401


async def test_refresh_grace_window_keeps_family_alive(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "refresh_token_reuse_grace_seconds",
        10,
    )

    first = (await login_user(client)).json()

    rotated = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert rotated.status_code == 200
    second = rotated.json()

    # A concurrent second tab using the old token gets 401, but the
    # freshly rotated token must remain usable.
    duplicate = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert duplicate.status_code == 401

    usable = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": second["refresh_token"]},
    )
    assert usable.status_code == 200


async def test_logout_revokes_refresh_token(client):
    tokens = (await login_user(client)).json()

    logged_out = await client.post(
        "/api/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logged_out.status_code == 204

    refresh = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 401


async def test_logout_all_invalidates_access_token(client):
    tokens = (await login_user(client)).json()

    logged_out = await client.post(
        "/api/auth/logout-all",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        },
    )
    assert logged_out.status_code == 204

    me = await client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        },
    )
    assert me.status_code == 401

    refresh = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 401


async def test_expired_and_tampered_access_tokens_are_rejected(
    client,
):
    tokens = (await login_user(client)).json()
    user_id = tokens["user"]["id"]

    expired = create_access_token(
        user_id,
        0,
        expires_delta=timedelta(seconds=-5),
    )

    expired_response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert expired_response.status_code == 401

    tampered_response = await client.get(
        "/api/auth/me",
        headers={
            "Authorization": (
                f"Bearer {tokens['access_token']}x"
            )
        },
    )
    assert tampered_response.status_code == 401


async def test_registration_can_be_disabled(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "auth_allow_registration",
        False,
    )

    response = await register_user(client)

    assert response.status_code == 403
    assert response.json()["detail"] == "Registration is disabled."


async def test_demo_mode_disables_registration_by_default(
    client,
    monkeypatch,
):
    monkeypatch.setattr(settings, "app_mode", "demo")
    monkeypatch.setattr(
        settings,
        "auth_allow_registration",
        None,
    )

    response = await register_user(client)

    assert response.status_code == 403


async def test_refresh_requires_a_token(client):
    response = await client.post("/api/auth/refresh")

    assert response.status_code == 401


async def test_cookie_delivery_and_rotation(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "refresh_token_delivery",
        "cookie",
    )

    logged_in = await login_user(client)
    assert logged_in.status_code == 200

    body = logged_in.json()
    assert "refresh_token" not in body

    set_cookie = logged_in.headers.get("set-cookie", "")
    lowered = set_cookie.lower()
    assert "httponly" in lowered
    assert "path=/api/auth" in lowered
    assert "samesite=lax" in lowered

    assert client.cookies.get("refresh_token")

    refreshed = await client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert "refresh_token" not in refreshed.json()

    logged_out = await client.post("/api/auth/logout")
    assert logged_out.status_code == 204
    assert client.cookies.get("refresh_token") is None

    after_logout = await client.post("/api/auth/refresh")
    assert after_logout.status_code == 401
