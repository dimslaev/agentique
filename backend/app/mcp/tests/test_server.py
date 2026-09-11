"""The bearer-token gate on the mounted MCP endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.platform.settings import settings

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


def test_the_right_token_gets_a_session(client: TestClient, token: str):
    response = client.post(
        MCP_URL,
        json=INITIALIZE,
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.usefixtures("token")
def test_a_wrong_token_is_rejected(client: TestClient):
    response = client.post(
        MCP_URL, json=INITIALIZE, headers={**HEADERS, "Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


@pytest.mark.usefixtures("token")
def test_no_token_is_rejected(client: TestClient):
    response = client.post(MCP_URL, json=INITIALIZE, headers=HEADERS)
    assert response.status_code == 401


def test_an_unconfigured_server_rejects_every_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    # A deploy that forgets MCP_TOKEN must serve 401s, not an open database.
    monkeypatch.setattr(settings, "MCP_TOKEN", None)
    response = client.post(
        MCP_URL, json=INITIALIZE, headers={**HEADERS, "Authorization": "Bearer "}
    )
    assert response.status_code == 401
