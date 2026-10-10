"""The weekly issue's markup, its render, and its hand-off to Resend.

Resend is stubbed: these pin what we send it (a draft, never a send, with
Resend's unsubscribe placeholder), that the post file parses, that the body's
marks render and nothing else does, and that the length and sourcing rules
hold.
"""

from __future__ import annotations

from datetime import date

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


TITLE = "What Ollama's MLX backend actually does"


def _issue(**overrides: str) -> broadcast.Issue:
    issue: broadcast.Issue = {
        "title": TITLE,
        "description": "And why people on three Macs got different numbers.",
        "topic": "local-ai",
        "body": BODY,
    }
    return {**issue, **overrides}  # type: ignore[typeddict-item]


def _post(
    title: str = TITLE,
    description: str = "And why people on three Macs got different numbers.",
    topic: str = "local-ai",
    body: str = BODY,
) -> str:
    return (
        f"---\ntitle: {title}\ndescription: {description}\ntopic: {topic}\n---\n"
        f"{body}\n"
    )


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


def test_a_post_parses_into_its_fields_and_body():
    assert broadcast.parse(_post()) == _issue()


def test_quoted_values_read_as_yaml_reads_them():
    post = (
        '---\ntitle: "Agents: \\"cheap\\" now"\n'
        "description: 'It''s a line'\ntopic: agents\n---\nBody"
    )
    issue = broadcast.parse(post)
    assert issue["title"] == 'Agents: "cheap" now'
    assert issue["description"] == "It's a line"
    assert issue["body"] == "Body"


@pytest.mark.parametrize(
    ("post", "message"),
    [
        ("title: t\n---\nb", "start with a ---"),
        ("---\ntitle: t\nb", "not closed"),
        ("---\nslug: t\n---\nb", "from the filename"),
        ("---\ntitle: a\ntitle: b\n---\nb", "twice"),
        ("---\n- title\n---\nb", "key: value"),
        ("---\ntitle: Agents: cheap now\n---\nb", "Quote the title"),
        ('---\ntitle: "open\n---\nb', "double-quoted"),
    ],
)
def test_a_malformed_post_is_refused(post: str, message: str):
    with pytest.raises(broadcast.IssueError, match=message):
        broadcast.parse(post)


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        (
            "What Ollama's MLX backend actually does",
            "what-ollama-s-mlx-backend-actually-does",
        ),
        ("  Café — 4-bit models, on GPUs!  ", "cafe-4-bit-models-on-gpus"),
        (
            "one two three four five six seven eight nine ten eleven twelve",
            "one-two-three-four-five-six-seven-eight-nine-ten-eleven",
        ),
    ],
)
def test_the_slug_comes_from_the_title(title: str, slug: str):
    assert broadcast.slugify(title) == slug
    assert len(slug) <= broadcast.MAX_SLUG


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
        ({"title": " "}, "title"),
        ({"title": "x" * 56}, "title is 56"),
        ({"title": "???"}, "slug"),
        ({"description": ""}, "description"),
        ({"description": "x" * 161}, "description is 161"),
        ({"topic": "Local AI"}, "kebab"),
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
    assert broadcast.draft(_post(), date(2026, 10, 9)) == (
        "Drafted broadcast b-1 (local-ai). Save the post, exactly as passed, at "
        "frontend/content/blog/2026-10-09-what-ollama-s-mlx-backend-actually-does.md"
    )
    [created] = configured["create"]
    assert created["audience_id"] == "audience"
    assert created["from"] == "agentique <news@agentique.example>"
    assert created["subject"] == TITLE
    assert created["name"] == "Weekly 2026-10-09 · local-ai"
    assert "send" not in created
    assert "And why people on three Macs" in created["html"]
    assert broadcast.UNSUBSCRIBE_PLACEHOLDER in created["html"]
    assert broadcast.UNSUBSCRIBE_PLACEHOLDER in created["text"]


def test_draft_refuses_before_reaching_resend(configured: dict[str, list]):
    with pytest.raises(broadcast.IssueError, match="title is 56"):
        broadcast.draft(_post(title="x" * 56))
    assert configured["create"] == []


def test_draft_without_resend_says_what_is_missing(
    configured: dict[str, list], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "RESEND_AUDIENCE_ID", None)
    with pytest.raises(broadcast.IssueError, match="RESEND_AUDIENCE_ID unset"):
        broadcast.draft(_post())
    assert configured["create"] == []
