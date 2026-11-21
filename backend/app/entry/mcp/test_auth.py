"""The tokens behind the scope gate: which scope each one carries.

The gate itself is pinned end to end in `test_server`.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.core.db.factories import create_random_user
from app.core.settings import settings
from app.entry.mcp import auth
from app.features.audience import service as audience


@pytest.mark.anyio
async def test_only_the_write_token_carries_the_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MCP_TOKEN", "read-token")
    monkeypatch.setattr(settings, "MCP_WRITE_TOKEN", "write-token")
    verifier = auth.SharedSecret()

    write = await verifier.verify_token("write-token")
    read = await verifier.verify_token("read-token")

    assert write is not None and write.scopes == [auth.WRITE_SCOPE]
    assert read is not None and read.scopes == []
    assert await verifier.verify_token("neither") is None


@pytest.mark.anyio
async def test_an_unset_write_token_matches_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deploy that forgets the variable must curate nothing, not let the read
    token publish — and an empty header must not match an empty setting."""
    monkeypatch.setattr(settings, "MCP_TOKEN", "read-token")
    monkeypatch.setattr(settings, "MCP_WRITE_TOKEN", None)
    verifier = auth.SharedSecret()

    assert await verifier.verify_token("") is None
    read = await verifier.verify_token("read-token")
    assert read is not None and read.scopes == []


@pytest.mark.anyio
async def test_a_user_token_carries_the_user_scope_and_its_owner(db: Session) -> None:
    user = create_random_user(db)
    token, _ = audience.issue_mcp_token(session=db, user_id=user.id)

    access = await auth.SharedSecret().verify_token(token)

    assert access is not None
    assert access.scopes == [auth.USER_SCOPE]
    assert access.client_id == str(user.id)


@pytest.mark.anyio
async def test_a_replaced_or_revoked_user_token_matches_nothing(db: Session) -> None:
    user = create_random_user(db)
    verifier = auth.SharedSecret()
    first, _ = audience.issue_mcp_token(session=db, user_id=user.id)
    second, _ = audience.issue_mcp_token(session=db, user_id=user.id)

    assert await verifier.verify_token(first) is None
    assert await verifier.verify_token(second) is not None

    audience.revoke_mcp_token(session=db, user_id=user.id)
    assert await verifier.verify_token(second) is None


@pytest.mark.anyio
async def test_the_token_of_an_inactive_account_matches_nothing(db: Session) -> None:
    user = create_random_user(db)
    token, _ = audience.issue_mcp_token(session=db, user_id=user.id)
    user.is_active = False
    db.add(user)
    db.commit()

    assert await auth.SharedSecret().verify_token(token) is None


@pytest.mark.anyio
async def test_a_shared_token_is_never_read_as_a_user_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shared tokens are checked first, so they never reach the lookup."""
    monkeypatch.setattr(settings, "MCP_TOKEN", "read-token")
    monkeypatch.setattr(settings, "MCP_WRITE_TOKEN", "write-token")

    def fail(token: str) -> None:
        raise AssertionError(f"looked up {token}")

    monkeypatch.setattr(auth, "_user_token_owner", fail)
    verifier = auth.SharedSecret()

    assert await verifier.verify_token("read-token") is not None
    assert await verifier.verify_token("write-token") is not None


def test_the_two_tokens_cannot_be_the_same_value() -> None:
    """The verifier checks the write token first, so a copy-paste that sets both
    to one value hands publishing rights to every holder of what the operator
    believes is a read-only credential. Nothing downstream would notice."""
    with pytest.raises(ValueError, match="same value"):
        settings.model_copy().model_validate(
            {
                **settings.model_dump(),
                "MCP_TOKEN": "one-secret",
                "MCP_WRITE_TOKEN": "one-secret",
            }
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
