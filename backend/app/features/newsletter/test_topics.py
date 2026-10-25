"""Tests for the newsletter's Resend topics: the list, the id lookup, and the
sync that creates the missing ones. Resend is stubbed, like test_broadcast."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import resend

from app.core.settings import settings
from app.features.newsletter import topics
from app.features.newsletter.model import IssueError

REPO = Path(__file__).resolve().parents[4]


def _list(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    monkeypatch.setattr(
        resend.Topics,
        "list",
        lambda _params=None: {
            "data": [{"id": f"t-{name}", "name": name} for name in names],
            "has_more": False,
        },
    )


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[dict[str, str]]]:
    monkeypatch.setattr(settings, "RESEND_API_KEY", "key")
    calls: dict[str, list[dict[str, str]]] = {"create": []}

    def create(params: dict[str, str]) -> dict[str, str]:
        calls["create"].append(params)
        return {"id": f"t-{params['name']}"}

    monkeypatch.setattr(resend.Topics, "create", create)
    return calls


def test_topics_match_the_feeds_slugs_and_labels() -> None:
    ts = (REPO / "frontend/src/features/feed/model/topics.ts").read_text()
    slugs = re.findall(r'slug: "([^"]+)"', ts)
    labels = re.findall(r'label: "([^"]+)"', ts)
    assert dict(zip(slugs, labels, strict=True)) == topics.TOPICS


@pytest.mark.usefixtures("configured")
def test_topic_ids_match_resend_topics_by_exact_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _list(monkeypatch, "Anthropic", "Open weights", "not one of ours")
    assert topics.topic_ids() == {
        "anthropic": "t-Anthropic",
        "open-weights": "t-Open weights",
    }


def test_topic_ids_refuse_without_resend_before_any_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RESEND_API_KEY", None)
    _list(monkeypatch, "Anthropic")
    with pytest.raises(IssueError, match="RESEND_API_KEY unset"):
        topics.topic_ids()


def test_create_missing_creates_only_what_resend_lacks(
    configured: dict[str, list[dict[str, str]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _list(monkeypatch, "Anthropic", "not one of ours")

    created = topics.create_missing()

    assert created == [
        (slug, f"t-{label}")
        for slug, label in topics.TOPICS.items()
        if slug != "anthropic"
    ]
    assert [p["name"] for p in configured["create"]] == [
        label for slug, label in topics.TOPICS.items() if slug != "anthropic"
    ]
    assert all(p["default_subscription"] == topics.OPT_IN for p in configured["create"])


def test_a_second_run_creates_nothing(
    configured: dict[str, list[dict[str, str]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _list(monkeypatch, *topics.TOPICS.values())

    assert topics.create_missing() == []
    assert configured["create"] == []
