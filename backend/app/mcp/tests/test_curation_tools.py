"""The write gate on the curation tools, and the two tokens behind it.

`sql_query` is read-only by the role it logs in as. The curation tools write as
`POSTGRES_USER`, so nothing but the token stands between a leaked read token and
a published article — which is what these pin.
"""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken

from app.mcp import tools
from app.mcp.server import SharedSecret
from app.platform.settings import settings

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
)


def _as(monkeypatch: pytest.MonkeyPatch, *scopes: str) -> None:
    """Answer the tools' scope check as a caller holding ``scopes``."""
    monkeypatch.setattr(
        tools,
        "get_access_token",
        lambda: AccessToken(token="t", client_id="c", scopes=list(scopes)),
    )


def _call(name: str):
    """Call one curation tool with throwaway arguments.

    The gate is the first thing each one does, so the arguments never matter:
    a caller without the scope is refused before any of them is read.
    """
    return {
        "list_candidates": lambda: tools.list_candidates(),
        "get_content": lambda: tools.get_content("https://example.com"),
        "similar": lambda: tools.similar("https://example.com"),
        "stories": lambda: tools.stories(),
        "check_link": lambda: tools.check_link("https://github.com/a/b"),
        "vocabulary": lambda: tools.vocabulary(),
        "approve": lambda: tools.approve(
            "https://example.com", 80, "r", "s", ["models"], "blog", []
        ),
        "reject": lambda: tools.reject("https://example.com", 20, "r"),
        "reject_many": lambda: tools.reject_many(
            [{"url": "https://example.com", "score": 20, "reason": "r"}]
        ),
    }[name]()


@pytest.mark.parametrize("name", WRITE_TOOLS)
def test_the_read_token_cannot_curate(monkeypatch: pytest.MonkeyPatch, name: str):
    _as(monkeypatch)
    with pytest.raises(ToolError, match="curation token"):
        _call(name)


@pytest.mark.parametrize("name", WRITE_TOOLS)
def test_an_unauthenticated_call_cannot_curate(
    monkeypatch: pytest.MonkeyPatch, name: str
):
    monkeypatch.setattr(tools, "get_access_token", lambda: None)
    with pytest.raises(ToolError, match="curation token"):
        _call(name)


def test_the_write_scope_gets_past_the_gate(monkeypatch: pytest.MonkeyPatch):
    """Past the gate it is an ordinary lookup, and a URL nobody queued is a
    message rather than a traceback."""
    _as(monkeypatch, tools.WRITE_SCOPE)
    with pytest.raises(ToolError, match="No candidate for"):
        tools.get_content("https://never-queued.example")


@pytest.mark.anyio
async def test_only_the_write_token_carries_the_scope(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "MCP_TOKEN", "read-token")
    monkeypatch.setattr(settings, "MCP_WRITE_TOKEN", "write-token")
    verifier = SharedSecret()

    write = await verifier.verify_token("write-token")
    read = await verifier.verify_token("read-token")

    assert write is not None and write.scopes == [tools.WRITE_SCOPE]
    assert read is not None and read.scopes == []
    assert await verifier.verify_token("neither") is None


@pytest.mark.anyio
async def test_an_unset_write_token_matches_nothing(monkeypatch: pytest.MonkeyPatch):
    """A deploy that forgets the variable must curate nothing, not let the read
    token publish — and an empty header must not match an empty setting."""
    monkeypatch.setattr(settings, "MCP_TOKEN", "read-token")
    monkeypatch.setattr(settings, "MCP_WRITE_TOKEN", None)
    verifier = SharedSecret()

    assert await verifier.verify_token("") is None
    read = await verifier.verify_token("read-token")
    assert read is not None and read.scopes == []


def test_the_two_tokens_cannot_be_the_same_value():
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


def test_check_link_refuses_what_it_does_not_read(monkeypatch: pytest.MonkeyPatch):
    _as(monkeypatch, tools.WRITE_SCOPE)
    with pytest.raises(ToolError, match="web_fetch"):
        tools.check_link("https://arxiv.org/abs/2609.01234")


def test_reject_many_reports_one_line_per_verdict(monkeypatch: pytest.MonkeyPatch):
    _as(monkeypatch, tools.WRITE_SCOPE)
    result = tools.reject_many(
        [
            {"url": "https://never-queued.example/1", "score": 20, "reason": "r"},
            {"url": "https://never-queued.example/2", "score": 20, "reason": "r"},
        ]
    )
    assert result.splitlines() == [
        "Skipped https://never-queued.example/1: "
        "No candidate for https://never-queued.example/1",
        "Skipped https://never-queued.example/2: "
        "No candidate for https://never-queued.example/2",
    ]
