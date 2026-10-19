"""GitHub API lookups: a failure reads as None, never as an answer."""

from __future__ import annotations

import httpx
import pytest

from app.core import github


def _answer(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> None:
    monkeypatch.setattr(github, "fetch_with_timeout", lambda url, **_: response)


def test_account_type_reads_the_type(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer(monkeypatch, httpx.Response(200, json={"type": "Organization"}))
    assert github.account_type("openai") == "Organization"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404),
        httpx.Response(200, json={"type": None}),
        httpx.Response(200, text="not json"),
    ],
)
def test_account_type_is_none_when_github_does_not_say(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response
) -> None:
    _answer(monkeypatch, response)
    assert github.account_type("someone") is None


def test_account_type_is_none_when_the_request_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_url: str, **_: object) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(github, "fetch_with_timeout", fail)
    assert github.account_type("someone") is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(403, text="API rate limit exceeded"),
        httpx.Response(404),
        httpx.Response(200, json=["not", "a", "repo"]),
    ],
)
def test_repo_for_is_none_rather_than_an_empty_repo(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response
) -> None:
    _answer(monkeypatch, response)
    assert github.repo_for("a", "b") is None
