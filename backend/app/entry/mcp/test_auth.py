"""The write gate on the curation tools, and the two tokens behind it.

`sql_query` is read-only by the role it logs in as. The curation tools write as
`POSTGRES_USER`, so nothing but the token stands between a leaked read token and
a published article — which is what these pin.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken
from sqlmodel import Session

from app.core.db.factories import create_random_user
from app.core.settings import settings
from app.entry.mcp import auth
from app.entry.mcp.approve import approve
from app.entry.mcp.check_link import check_link
from app.entry.mcp.close_story import close_story
from app.entry.mcp.draft_issue import draft_issue
from app.entry.mcp.get_content import get_content
from app.entry.mcp.list_candidates import list_candidates
from app.entry.mcp.reject import reject
from app.entry.mcp.reject_many import reject_many
from app.entry.mcp.related import related
from app.entry.mcp.save_story import save_story
from app.entry.mcp.similar import similar
from app.entry.mcp.stories import stories
from app.entry.mcp.story_candidates import story_candidates
from app.entry.mcp.vocabulary import vocabulary
from app.entry.mcp.week import week
from app.features.audience import service as audience

WRITE_TOOLS = (
    "list_candidates",
    "get_content",
    "similar",
    "stories",
    "check_link",
    "vocabulary",
    "approve",
    "reject",
    "reject_many",
    "week",
    "related",
    "draft_issue",
    "story_candidates",
    "save_story",
    "close_story",
)


def _as(monkeypatch: pytest.MonkeyPatch, *scopes: str) -> None:
    """Answer the tools' scope check as a caller holding ``scopes``."""
    monkeypatch.setattr(
        auth,
        "get_access_token",
        lambda: AccessToken(token="t", client_id="c", scopes=list(scopes)),
    )


def _call(name: str) -> object:
    """Call one curation tool with throwaway arguments.

    The gate is the first thing each one does, so the arguments never matter:
    a caller without the scope is refused before any of them is read.
    """
    calls: dict[str, Callable[[], object]] = {
        "list_candidates": lambda: list_candidates(),
        "get_content": lambda: get_content("https://example.com"),
        "similar": lambda: similar("https://example.com"),
        "stories": lambda: stories(),
        "check_link": lambda: check_link("https://github.com/a/b"),
        "vocabulary": lambda: vocabulary(),
        "approve": lambda: approve("https://example.com", 80, "r", "s", "post", []),
        "reject": lambda: reject("https://example.com", 20, "r"),
        "reject_many": lambda: reject_many(
            [{"url": "https://example.com", "score": 20, "reason": "r"}]
        ),
        "week": lambda: week(),
        "related": lambda: related("https://example.com"),
        "draft_issue": lambda: draft_issue("---\ntitle: t\n---\nb"),
        "story_candidates": lambda: story_candidates(),
        "save_story": lambda: save_story("s", "n", "b", []),
        "close_story": lambda: close_story("s"),
    }
    return calls[name]()


@pytest.mark.parametrize("name", WRITE_TOOLS)
def test_the_read_token_cannot_curate(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    _as(monkeypatch)
    with pytest.raises(ToolError, match="curation token"):
        _call(name)


@pytest.mark.parametrize("name", WRITE_TOOLS)
def test_an_unauthenticated_call_cannot_curate(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setattr(auth, "get_access_token", lambda: None)
    with pytest.raises(ToolError, match="curation token"):
        _call(name)


def test_the_write_scope_gets_past_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Past the gate it is an ordinary lookup, and a URL nobody queued is a
    message rather than a traceback."""
    _as(monkeypatch, auth.WRITE_SCOPE)
    with pytest.raises(ToolError, match="No candidate for"):
        get_content("https://never-queued.example")


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


@pytest.mark.parametrize("name", WRITE_TOOLS)
def test_the_user_scope_cannot_curate(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Behind the server-wide gate, each write tool refuses the scope itself."""
    _as(monkeypatch, auth.USER_SCOPE)
    with pytest.raises(ToolError, match="curation token"):
        _call(name)


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
