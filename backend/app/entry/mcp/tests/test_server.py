"""The bearer-token gate on the mounted MCP endpoint, end to end over HTTP."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.settings import settings

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


def _call_tool(
    client: TestClient, token: str, name: str, arguments: dict[str, object]
) -> dict[str, object]:
    """Open a session with ``token`` and call one tool, as an MCP client would.

    Returns the JSON-RPC ``result``. A refused tool call is still a 200 with
    ``isError`` set: the gate inside the tool answers, not the HTTP layer.
    """
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
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = next(
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    )
    result: dict[str, object] = json.loads(data)["result"]
    return result


def _text(result: dict[str, object]) -> str:
    content = result["content"]
    assert isinstance(content, list)
    return str(content[0]["text"])


@pytest.mark.usefixtures("both_tokens")
def test_the_read_token_is_refused_by_a_write_tool(client: TestClient) -> None:
    result = _call_tool(
        client, READ_TOKEN, "get_content", {"url": "https://never-queued.example"}
    )
    assert result["isError"] is True
    assert "curation token" in _text(result)


@pytest.mark.usefixtures("both_tokens")
def test_the_write_token_gets_past_the_gate(client: TestClient) -> None:
    # Past the gate it is an ordinary lookup, so the refusal is the candidate's.
    result = _call_tool(
        client, WRITE_TOKEN, "get_content", {"url": "https://never-queued.example"}
    )
    assert result["isError"] is True
    assert "No candidate for" in _text(result)


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

    result = _call_tool(
        client, READ_TOKEN, "get_content", {"url": "https://never-queued.example"}
    )
    assert result["isError"] is True
    assert "curation token" in _text(result)
