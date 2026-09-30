"""The weekly issue's render and its hand-off to Resend.

Resend is stubbed: these pin what we send it (a draft, never a send, with the
unsubscribe placeholder in the broadcast and not in the preview) and that
nothing the agent writes reaches the HTML unescaped.
"""

from __future__ import annotations

from datetime import date

import pytest
import resend

from app.newsletter import broadcast
from app.platform.settings import settings

DAY = date(2026, 10, 2)


def _issue(**overrides: object) -> broadcast.Issue:
    issue: broadcast.Issue = {
        "subject": "Ollama runs on MLX",
        "preheader": "And a week of agent tooling.",
        "intro": "Three things shipped.\n\nOne of them you can run today.",
        "stories": [
            {
                "title": "Ollama 0.9 ships an MLX backend",
                "url": "https://ollama.example/blog/mlx",
                "body": "Twice the tokens per second.\n\nMeasured on an M3.",
                "further": [
                    {
                        "title": "I benchmarked it",
                        "url": "https://writer.example/mlx",
                        "by": "A Writer",
                        "note": "Numbers on three Macs.",
                    }
                ],
            }
        ],
        "quick_hits": [
            {
                "title": "A kernel post",
                "url": "https://blog.example/kernels",
                "line": "Fused attention, explained.",
            }
        ],
    }
    return {**issue, **overrides}  # type: ignore[typeddict-item]


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    monkeypatch.setattr(settings, "RESEND_API_KEY", "key")
    monkeypatch.setattr(settings, "RESEND_AUDIENCE_ID", "audience")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "news@agentique.example")
    monkeypatch.setattr(settings, "EMAILS_FROM_NAME", "agentique")
    monkeypatch.setattr(settings, "NEWSLETTER_PREVIEW_EMAIL", "me@agentique.example")
    calls: dict[str, list] = {"create": [], "send": [], "email": []}

    def create(params):
        calls["create"].append(params)
        return {"id": "b-1"}

    monkeypatch.setattr(resend.Broadcasts, "create", create)
    monkeypatch.setattr(resend.Broadcasts, "send", calls["send"].append)
    monkeypatch.setattr(resend.Emails, "send", calls["email"].append)
    return calls


def test_the_html_has_every_story_link_and_the_unsubscribe_link():
    html = broadcast.render_html(_issue(), DAY, broadcast.UNSUBSCRIBE_PLACEHOLDER)
    for url in (
        "https://ollama.example/blog/mlx",
        "https://writer.example/mlx",
        "https://blog.example/kernels",
    ):
        assert f'href="{url}"' in html
    assert f'href="{broadcast.UNSUBSCRIBE_PLACEHOLDER}"' in html
    assert "2 October 2026" in html
    assert "<p" in html and "Measured on an M3." in html


def test_what_the_agent_writes_is_escaped():
    issue = _issue(intro="<script>alert(1)</script> & more")
    html = broadcast.render_html(issue, DAY, "#")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_the_text_twin_carries_the_links():
    text = broadcast.render_text(_issue(), "https://unsubscribe.example")
    assert "https://ollama.example/blog/mlx" in text
    assert "- I benchmarked it (A Writer) - Numbers on three Macs." in text
    assert text.endswith("Unsubscribe: https://unsubscribe.example")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"subject": " "}, "subject"),
        ({"intro": ""}, "intro"),
        ({"stories": []}, "1-6 stories"),
        (
            {
                "stories": [
                    {"title": "t", "url": "ollama.example", "body": "b", "further": []}
                ]
            },
            "no http",
        ),
        (
            {
                "stories": [
                    {
                        "title": "t",
                        "url": "https://a.example",
                        "body": "",
                        "further": [],
                    }
                ]
            },
            "no body",
        ),
    ],
)
def test_an_issue_a_reader_should_not_get_is_refused(overrides: dict, message: str):
    with pytest.raises(broadcast.IssueError, match=message):
        broadcast.validate(_issue(**overrides))


def test_draft_creates_a_broadcast_and_mails_a_preview(configured: dict[str, list]):
    result = broadcast.draft(_issue(), DAY)

    assert result == "Drafted broadcast b-1; preview sent to me@agentique.example."
    [created] = configured["create"]
    assert created["audience_id"] == "audience"
    assert created["from"] == "agentique <news@agentique.example>"
    assert "send" not in created
    assert broadcast.UNSUBSCRIBE_PLACEHOLDER in created["html"]
    assert broadcast.UNSUBSCRIBE_PLACEHOLDER in created["text"]
    [preview] = configured["email"]
    assert preview["to"] == "me@agentique.example"
    assert preview["subject"] == "[Draft] Ollama runs on MLX"
    assert broadcast.UNSUBSCRIBE_PLACEHOLDER not in preview["html"]
    assert configured["send"] == []


@pytest.mark.usefixtures("configured")
def test_a_failed_preview_still_leaves_the_draft(monkeypatch: pytest.MonkeyPatch):
    def fail(_params):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(resend.Emails, "send", fail)
    result = broadcast.draft(_issue(), DAY)
    assert result == "Drafted broadcast b-1; preview failed: rate limited."


def test_draft_without_resend_says_what_is_missing(
    configured: dict[str, list], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "RESEND_AUDIENCE_ID", None)
    with pytest.raises(broadcast.IssueError, match="RESEND_AUDIENCE_ID unset"):
        broadcast.draft(_issue(), DAY)
    assert configured["create"] == []


def test_send_sends_the_broadcast(configured: dict[str, list]):
    assert broadcast.send("b-1") == "Sent broadcast b-1."
    assert configured["send"] == [{"broadcast_id": "b-1"}]
