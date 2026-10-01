"""The weekly issue's markup, its render, and its hand-off to Resend.

Resend is stubbed: these pin what we send it (a draft, never a send, with
Resend's unsubscribe placeholder), that the body's marks render and nothing
else does, and that the length and sourcing rules hold.
"""

from __future__ import annotations

import pytest
import resend

from app.newsletter import broadcast
from app.platform.settings import settings

FILLER = " ".join(["word"] * 70)
BODY = (
    "I kept seeing [the MLX backend](https://ollama.example/blog/mlx) this week,\n"
    f"so I tried to work out what it changes. {FILLER}\n\n"
    "- [a benchmark](https://writer.example/mlx) on three Macs\n"
    "- [a repo](https://github.com/someone/ollama-ci) that runs it in CI\n\n"
    f"Try `ollama run llama3` and see for yourself. {FILLER}"
)
REPO = "https://github.com/someone/ollama-ci"


def _issue(**overrides: str) -> broadcast.Issue:
    issue: broadcast.Issue = {
        "label": "Ollama on MLX",
        "subject": "What Ollama's MLX backend actually does",
        "preheader": "And why people on three Macs got different numbers.",
        "body": BODY,
    }
    return {**issue, **overrides}  # type: ignore[typeddict-item]


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    monkeypatch.setattr(settings, "RESEND_API_KEY", "key")
    monkeypatch.setattr(settings, "RESEND_AUDIENCE_ID", "audience")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "news@agentique.example")
    monkeypatch.setattr(settings, "EMAILS_FROM_NAME", "agentique")
    monkeypatch.setattr(settings, "FRONTEND_HOST", "https://agentique.example")
    calls: dict[str, list] = {"create": []}

    def create(params):
        calls["create"].append(params)
        return {"id": "b-1"}

    monkeypatch.setattr(resend.Broadcasts, "create", create)
    return calls


def test_blocks_are_paragraphs_and_lists():
    assert broadcast.blocks("One\nline.\n\n- a\n- b\n\n- a\nnot a list\n\n\n") == [
        {"kind": "p", "lines": ["One line."]},
        {"kind": "ul", "lines": ["a", "b"]},
        {"kind": "p", "lines": ["- a not a list"]},
    ]


def test_inline_html_links_code_and_escapes_the_rest():
    html = broadcast.inline_html("<b>[see](https://a.example/?x=1&y=2)</b> `a<b`")
    assert html.startswith('&lt;b&gt;<a href="https://a.example/?x=1&amp;y=2"')
    assert ">see</a>&lt;/b&gt;" in html
    assert "a&lt;b</code>" in html


def test_inline_text_spells_the_link_out():
    line = "Read [this](https://a.example) and run `ls`."
    assert broadcast.inline_text(line) == "Read this (https://a.example) and run ls."


def test_word_count_skips_the_urls():
    assert broadcast.word_count("[two words](https://a.example/long/path) `x`") == 3


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"subject": " "}, "subject"),
        ({"label": ""}, "label"),
        ({"body": "Too short, [a](https://a.example)."}, "one to two minutes"),
        ({"body": BODY + " " + " ".join(["more"] * 500)}, "one to two minutes"),
        ({"body": BODY.replace("https://writer.example", "writer.example")}, "http"),
        ({"body": BODY.replace(REPO, "https://ollama.example/blog/mlx")}, "at least 3"),
    ],
)
def test_an_issue_a_reader_should_not_get_is_refused(overrides: dict, message: str):
    with pytest.raises(broadcast.IssueError, match=message):
        broadcast.validate(_issue(**overrides))


@pytest.mark.usefixtures("configured")
def test_the_html_is_the_wordmark_the_prose_and_two_links():
    html = broadcast.render_html(_issue())
    assert ">agentique</a>" in html
    for url in (
        "https://agentique.example",
        "https://ollama.example/blog/mlx",
        "https://writer.example/mlx",
        REPO,
        "https://agentique.example/feed",
        broadcast.UNSUBSCRIBE_PLACEHOLDER,
    ):
        assert f'href="{url}"' in html
    assert "<li" in html and "<code" in html


@pytest.mark.usefixtures("configured")
def test_the_text_twin_ends_with_the_feed_and_unsubscribe():
    text = broadcast.render_text(_issue())
    assert "I kept seeing the MLX backend (https://ollama.example/blog/mlx)" in text
    assert "- a benchmark (https://writer.example/mlx) on three Macs" in text
    assert text.endswith(
        "The feed: https://agentique.example/feed\n"
        f"Unsubscribe: {broadcast.UNSUBSCRIBE_PLACEHOLDER}"
    )


def test_draft_creates_a_named_draft_broadcast(configured: dict[str, list]):
    assert broadcast.draft(_issue()) == "Drafted broadcast b-1 (Ollama on MLX)."
    [created] = configured["create"]
    assert created["audience_id"] == "audience"
    assert created["from"] == "agentique <news@agentique.example>"
    assert created["subject"] == "What Ollama's MLX backend actually does"
    assert created["name"].endswith(" · Ollama on MLX")
    assert "send" not in created
    assert broadcast.UNSUBSCRIBE_PLACEHOLDER in created["html"]
    assert broadcast.UNSUBSCRIBE_PLACEHOLDER in created["text"]


def test_draft_without_resend_says_what_is_missing(
    configured: dict[str, list], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "RESEND_AUDIENCE_ID", None)
    with pytest.raises(broadcast.IssueError, match="RESEND_AUDIENCE_ID unset"):
        broadcast.draft(_issue())
    assert configured["create"] == []
