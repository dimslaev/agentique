"""Tests for self-service account endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.db.factories import (
    create_random_user,
    random_email,
    user_authentication_headers,
)
from app.core.db.mcp_token import McpToken
from app.core.db.user import User
from app.core.security import hash_mcp_token
from app.core.settings import settings


def test_get_users_superuser_me(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"]
    assert current_user["email"] == settings.FIRST_SUPERUSER


def test_get_users_normal_user_me(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"] is False
    assert current_user["email"] == settings.EMAIL_TEST_USER


def test_update_user_me(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    full_name = "Updated Name"
    email = random_email()
    data = {"full_name": full_name, "email": email}
    r = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()
    assert updated_user["email"] == email
    assert updated_user["full_name"] == full_name

    user_query = select(User).where(User.email == email)
    user_db = db.exec(user_query).first()
    assert user_db
    assert user_db.email == email
    assert user_db.full_name == full_name


def test_update_user_me_email_exists(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    user = create_random_user(db)

    data = {"email": user.email}
    r = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "User with this email already exists"


def test_delete_user_me(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    user_id = user.id
    headers = user_authentication_headers(user)

    r = client.delete(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
    )
    assert r.status_code == 200
    deleted_user = r.json()
    assert deleted_user["message"] == "User deleted successfully"
    result = db.exec(select(User).where(User.id == user_id)).first()
    assert result is None

    user_query = select(User).where(User.id == user_id)
    user_db = db.exec(user_query).first()
    assert user_db is None


def test_delete_user_me_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/users/me",
        headers=superuser_token_headers,
    )
    assert r.status_code == 403
    response = r.json()
    assert response["detail"] == "Super users are not allowed to delete themselves"


MCP_TOKEN_URL = f"{settings.API_V1_STR}/users/me/mcp-token"


def test_create_mcp_token_returns_it_once_and_stores_only_the_hash(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db)
    headers = user_authentication_headers(user)

    assert client.get(MCP_TOKEN_URL, headers=headers).json() == {
        "exists": False,
        "created_at": None,
    }

    created = client.post(MCP_TOKEN_URL, headers=headers)
    assert created.status_code == 200
    token = created.json()["token"]
    assert token.startswith("agq_")

    row = db.get(McpToken, user.id)
    assert row is not None
    assert row.token_hash == hash_mcp_token(token)
    assert row.token_hash not in created.text

    status = client.get(MCP_TOKEN_URL, headers=headers)
    assert status.json()["exists"] is True
    assert set(status.json()) == {"exists", "created_at"}
    assert token not in status.text
    assert row.token_hash not in status.text


def test_create_mcp_token_replaces_the_earlier_one(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db)
    headers = user_authentication_headers(user)

    first = client.post(MCP_TOKEN_URL, headers=headers).json()["token"]
    second = client.post(MCP_TOKEN_URL, headers=headers).json()["token"]

    assert first != second
    db.expire_all()
    rows = db.exec(select(McpToken).where(McpToken.user_id == user.id)).all()
    assert [row.token_hash for row in rows] == [hash_mcp_token(second)]


def test_revoke_mcp_token(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    headers = user_authentication_headers(user)
    client.post(MCP_TOKEN_URL, headers=headers)

    revoked = client.delete(MCP_TOKEN_URL, headers=headers)
    assert revoked.status_code == 200
    assert client.get(MCP_TOKEN_URL, headers=headers).json()["exists"] is False
    db.expire_all()
    assert db.get(McpToken, user.id) is None

    again = client.delete(MCP_TOKEN_URL, headers=headers)
    assert again.status_code == 200


def test_mcp_token_needs_a_signed_in_user(client: TestClient) -> None:
    for method in ("get", "post", "delete"):
        assert client.request(method, MCP_TOKEN_URL).status_code in (401, 403)


def test_deleting_the_account_deletes_its_mcp_token(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db)
    user_id = user.id
    headers = user_authentication_headers(user)
    client.post(MCP_TOKEN_URL, headers=headers)

    deleted = client.delete(f"{settings.API_V1_STR}/users/me", headers=headers)
    assert deleted.status_code == 200
    db.expire_all()
    assert db.get(McpToken, user_id) is None
