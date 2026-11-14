"""The bearer-token gate on the mounted MCP endpoint, end to end over HTTP."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, delete

from app.core.db.factories import (
    create_random_article,
    create_random_tag,
    create_random_user,
    random_lower_string,
    tag_article,
)
from app.core.db.tag import ArticleTag
from app.core.settings import settings
from app.entry.mcp import auth
from app.entry.mcp.server import mcp
from app.features.audience import service as audience

MCP_URL = "/mcp/"
HEADERS = {"Accept": "application/json, text/event-stream"}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}


@pytest.fixture
def token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "MCP_TOKEN", "test-mcp-token")
    return "test-mcp-token"


def test_the_right_token_gets_a_session(client: TestClient, token: str) -> None:
    response = client.post(
        MCP_URL,
        json=INITIALIZE,
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.usefixtures("token")
def test_a_wrong_token_is_rejected(client: TestClient) -> None:
    response = client.post(
        MCP_URL, json=INITIALIZE, headers={**HEADERS, "Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


@pytest.mark.usefixtures("token")
def test_no_token_is_rejected(client: TestClient) -> None:
    response = client.post(MCP_URL, json=INITIALIZE, headers=HEADERS)
    assert response.status_code == 401


def test_an_unconfigured_server_rejects_every_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A deploy that forgets MCP_TOKEN must serve 401s, not an open database.
    monkeypatch.setattr(settings, "MCP_TOKEN", None)
    response = client.post(
        MCP_URL, json=INITIALIZE, headers={**HEADERS, "Authorization": "Bearer "}
    )
    assert response.status_code == 401


READ_TOKEN = "test-read-token"
WRITE_TOKEN = "test-write-token"


@pytest.fixture
def both_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MCP_TOKEN", READ_TOKEN)
    monkeypatch.setattr(settings, "MCP_WRITE_TOKEN", WRITE_TOKEN)


def _request(
    client: TestClient, token: str, method: str, params: dict[str, object]
) -> str:
    """Open a session with ``token`` and send one request, as an MCP client would.

    Returns the JSON of the response message."""
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    opened = client.post(MCP_URL, json=INITIALIZE, headers=headers)
    assert opened.status_code == 200
    headers["mcp-session-id"] = opened.headers["mcp-session-id"]
    client.post(
        MCP_URL,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=headers,
    )
    response = client.post(
        MCP_URL,
        json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params},
        headers=headers,
    )
    assert response.status_code == 200
    return next(
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    )


def _call_tool(
    client: TestClient, token: str, name: str, arguments: dict[str, object]
) -> tuple[bool, str]:
    """Call one tool and return the result's ``isError`` and its text.

    A refused tool call is still a 200: the gate inside the tool answers, not
    the HTTP layer.
    """
    message = _request(
        client, token, "tools/call", {"name": name, "arguments": arguments}
    )
    result = json.loads(message)["result"]
    return result["isError"], result["content"][0]["text"]


def _list_tools(client: TestClient, token: str) -> set[str]:
    message = _request(client, token, "tools/list", {})
    return {tool["name"] for tool in json.loads(message)["result"]["tools"]}


@pytest.mark.usefixtures("both_tokens")
def test_the_read_token_is_refused_by_a_write_tool(client: TestClient) -> None:
    is_error, text = _call_tool(
        client, READ_TOKEN, "get_content", {"url": "https://never-queued.example"}
    )
    assert is_error
    assert "curation token" in text


@pytest.mark.usefixtures("both_tokens")
def test_the_write_token_gets_past_the_gate(client: TestClient) -> None:
    # Past the gate it is an ordinary lookup, so the refusal is the candidate's.
    is_error, text = _call_tool(
        client, WRITE_TOKEN, "get_content", {"url": "https://never-queued.example"}
    )
    assert is_error
    assert "No candidate for" in text


def test_an_unset_write_token_opens_no_write_tool(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MCP_TOKEN", READ_TOKEN)
    monkeypatch.setattr(settings, "MCP_WRITE_TOKEN", None)

    stale = client.post(
        MCP_URL,
        json=INITIALIZE,
        headers={**HEADERS, "Authorization": f"Bearer {WRITE_TOKEN}"},
    )
    assert stale.status_code == 401

    is_error, text = _call_tool(
        client, READ_TOKEN, "get_content", {"url": "https://never-queued.example"}
    )
    assert is_error
    assert "curation token" in text


# Read from the server, not typed out here, so a tool added later is covered
# without anyone remembering to add it.
REGISTERED_TOOLS = sorted(tool.name for tool in asyncio.run(mcp.list_tools()))


@pytest.fixture
def user_token(db: Session) -> str:
    user = create_random_user(db)
    token, _ = audience.issue_mcp_token(session=db, user_id=user.id)
    return token


def test_the_server_has_tools_to_refuse() -> None:
    assert {"sql_query", "web_fetch", "web_search", "approve"} <= set(REGISTERED_TOOLS)


@pytest.mark.usefixtures("both_tokens")
def test_a_user_token_lists_only_its_own_tools(
    client: TestClient, user_token: str
) -> None:
    assert _list_tools(client, user_token) == {"search", "tags", "sql_query"}
    assert auth.USER_TOOLS == {"search", "tags", "sql_query"}


@pytest.mark.usefixtures("both_tokens")
@pytest.mark.parametrize("name", sorted(set(REGISTERED_TOOLS) - auth.USER_TOOLS))
def test_a_user_token_is_refused_by_every_other_tool(
    client: TestClient, user_token: str, name: str
) -> None:
    """Refused by the gate before the arguments are read, so none are sent. A
    tool that got past it would complain about its arguments instead."""
    is_error, text = _call_tool(client, user_token, name, {})
    assert is_error
    assert "Authorization failed" in text


@pytest.mark.usefixtures("both_tokens", "reader_sql")
def test_a_user_token_chains_tags_into_search_and_sql(
    client: TestClient,
    user_token: str,
    db: Session,
    made: dict[str, list[int]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.features.catalog.search.embed", lambda _text: [0.05] * 256)
    word = random_lower_string()
    article = create_random_article(
        db, title=f"About {word}", content=f"Private body mentioning {word}."
    )
    assert article.id is not None
    made["articles"].append(article.id)
    made["publishers"].append(article.publisher_id)
    tag = create_random_tag(db)
    tag_article(db, article, tag)

    try:
        is_error, text = _call_tool(client, user_token, "tags", {})
        assert not is_error
        assert tag.slug in text

        is_error, text = _call_tool(
            client, user_token, "search", {"q": word, "tags": [tag.slug]}
        )
        assert not is_error
        assert article.url in text

        is_error, text = _call_tool(
            client,
            user_token,
            "sql_query",
            {
                "sql": "SELECT a.url FROM article a "
                "JOIN article_tag x ON x.article_id = a.id "
                f"JOIN tag t ON t.id = x.tag_id WHERE t.slug = '{tag.slug}'"
            },
        )
        assert not is_error
        assert json.loads(text)["rows"] == [{"url": article.url}]

        is_error, text = _call_tool(
            client, user_token, "sql_query", {"sql": 'SELECT email FROM public."user"'}
        )
        assert is_error
        assert "permission denied" in text
    finally:
        db.exec(delete(ArticleTag).where(col(ArticleTag.tag_id) == tag.id))
        db.delete(tag)
        db.commit()


@pytest.mark.usefixtures("both_tokens")
def test_the_shared_tokens_still_list_every_tool(client: TestClient) -> None:
    assert _list_tools(client, READ_TOKEN) == set(REGISTERED_TOOLS)
    assert _list_tools(client, WRITE_TOKEN) == set(REGISTERED_TOOLS)


@pytest.mark.usefixtures("both_tokens")
def test_a_user_token_reaches_only_the_tools_it_is_allowed(
    client: TestClient, user_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Being on the list lifts the user gate and nothing else: a curation tool
    still asks for the write scope."""
    monkeypatch.setattr(auth, "USER_TOOLS", frozenset({"get_content"}))

    assert _list_tools(client, user_token) == {"get_content"}
    is_error, text = _call_tool(
        client, user_token, "get_content", {"url": "https://never-queued.example"}
    )
    assert is_error
    assert "curation token" in text
    is_error, text = _call_tool(client, user_token, "search", {"q": "x"})
    assert is_error
    assert "Authorization failed" in text


@pytest.mark.usefixtures("both_tokens")
def test_a_revoked_user_token_is_rejected(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    token, _ = audience.issue_mcp_token(session=db, user_id=user.id)
    audience.revoke_mcp_token(session=db, user_id=user.id)

    response = client.post(
        MCP_URL,
        json=INITIALIZE,
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.usefixtures("both_tokens")
def test_a_user_token_is_rate_limited_and_a_shared_token_is_not(
    client: TestClient, user_token: str
) -> None:
    for _ in range(20):
        _, text = _call_tool(client, user_token, "web_fetch", {})
        assert "Authorization failed" in text
    is_error, text = _call_tool(client, user_token, "tags", {})
    assert is_error
    assert "Rate limit reached: 20 calls a minute" in text

    for _ in range(21):
        _, text = _call_tool(
            client, READ_TOKEN, "get_content", {"url": "https://x.example"}
        )
        assert "curation token" in text
