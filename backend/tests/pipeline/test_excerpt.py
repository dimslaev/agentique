"""to_excerpt: the card text, now that no LLM writes it.

This is the last thing between raw feed content — markdown, HTML, emoji,
whatever the publisher shipped — and what a reader sees. It has no model to
blame and no validator downstream, so everything it must strip is pinned here.
"""

from __future__ import annotations

import pytest

from pipeline.excerpt import EXCERPT_CHARS, to_excerpt, truncate_on_word

# ─── markup removal ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected", "why"),
    [
        ("<p>Hello <b>world</b></p><div>more</div>", "Hello world more", "html tags"),
        ("Use &lt;script&gt; tags &amp; entities", "Use tags & entities", "entities"),
        ("<script>alert('x')</script>Real text", "Real text", "script body"),
        ("<style>.a{color:red}</style>Copy here", "Copy here", "style body"),
        ("<!-- hidden -->Shown text", "Shown text", "html comment"),
        ("Intro.\n```py\nsecret()\n```\nOutro.", "Intro. Outro.", "fenced code"),
        ("![alt](http://x.png) Body text", "Body text", "markdown image"),
        ("See [the docs](http://x.com) now", "See the docs now", "markdown link"),
        ("# Big Title\n## Sub\nBody", "Big Title Sub Body", "markdown headings"),
        ("- one\n- two\n1. three", "one two three", "list markers"),
        ("> quoted\nnormal", "quoted normal", "blockquote"),
        ("text\n---\nmore", "text more", "horizontal rule"),
        ("| a | b |\n|---|---|\n| 1 | 2 |", "a b 1 2", "table pipes"),
        ("This is **bold** and `code`", "This is bold and code", "emphasis"),
        ("[1]: https://x.com/y\nActual body", "Actual body", "link reference def"),
        ("a\n\n\nb\t\tc   d", "a b c d", "whitespace collapse"),
    ],
)
def test_strips(raw: str, expected: str, why: str) -> None:
    assert to_excerpt(raw) == expected, why


def test_escaped_markup_does_not_survive_as_visible_brackets() -> None:
    """Feeds routinely double-escape their HTML. Decoding without a second tag
    pass would leave `<p>` sitting in the reader's face."""
    assert to_excerpt("&lt;p&gt;Escaped body&lt;/p&gt;") == "Escaped body"


def test_prose_pipe_is_not_treated_as_a_table() -> None:
    """A lone pipe in a sentence usually means "or" — only a line that is
    pipe-delimited end to end is a table row."""
    assert to_excerpt("choose foo | bar to filter") == "choose foo | bar to filter"


# ─── emoji ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        "Ship it 🚀 today",
        "Done ✅ and shipped",
        "Party 🎉🎊 time",
        "Family 👨‍👩‍👧‍👦 emoji with joiners",
        "Flag 🇺🇸 sequence",
        "Skin tone 👋🏽 modifier",
        "Heart ❤️ with variation selector",
    ],
)
def test_removes_emoji(raw: str) -> None:
    out = to_excerpt(raw)
    assert out.isascii(), f"non-ascii survived: {out!r}"


def test_keeps_the_words_around_the_emoji() -> None:
    assert to_excerpt("Ship it 🚀 today 🎉 for real") == "Ship it today for real"


# ─── residual noise ─────────────────────────────────────────────────────────


def test_strips_ascii_art_banners() -> None:
    """290 occurrences in the prod dump: the block-drawing logo at the top of a
    README, which markup stripping leaves completely intact."""
    assert (
        to_excerpt("\u2588\u2588\u2588 LOGO \u2588\u2588\u2588\nReal text")
        == "LOGO Real text"
    )
    assert to_excerpt("\u250c\u2500\u2500\u2510\nBoxed text") == "Boxed text"


def test_strips_zero_width_characters() -> None:
    """Invisible, so nothing looks wrong — but they break copy-paste and any
    substring search over the excerpt."""
    assert to_excerpt("a\u200bb\u200cc\u200dd\ufeffe") == "abcde"


def test_normalizes_the_non_breaking_hyphen() -> None:
    assert to_excerpt("non\u2011breaking hyphen") == "non-breaking hyphen"


def test_keeps_a_middle_dot_separator() -> None:
    """Not noise — publishers use it between real links."""
    assert (
        to_excerpt("Docs \u00b7 Changelog \u00b7 PyPI")
        == "Docs \u00b7 Changelog \u00b7 PyPI"
    )


def test_keeps_cjk() -> None:
    """The old summarizer rejected CJK because the *model* was drifting out of
    English. An excerpt only repeats the source, so a Chinese article should
    read as Chinese rather than come out blank."""
    assert to_excerpt("\u4e2d\u6587\u6587\u7ae0") == "\u4e2d\u6587\u6587\u7ae0"


# ─── truncation ─────────────────────────────────────────────────────────────


def test_short_text_is_untouched_and_has_no_ellipsis() -> None:
    assert to_excerpt("A short line.") == "A short line."


def test_cuts_on_a_word_boundary() -> None:
    assert to_excerpt("alpha beta gamma delta", 16) == "alpha beta..."


def test_strips_punctuation_left_dangling_by_the_cut() -> None:
    assert to_excerpt("alpha beta, gamma", 14) == "alpha..."


def test_a_single_word_longer_than_the_limit_is_still_cut() -> None:
    """A URL or a hash. An ugly excerpt beats no excerpt."""
    assert to_excerpt("x" * 50, 10) == "xxxxxxx..."


@pytest.mark.parametrize("limit", [4, 10, 50, 280, 1000])
def test_never_exceeds_the_limit(limit: int) -> None:
    assert len(to_excerpt("word " * 500, limit)) <= limit


def test_default_limit_is_respected() -> None:
    assert len(to_excerpt("word " * 500)) <= EXCERPT_CHARS


def test_truncate_on_word_leaves_exact_fit_alone() -> None:
    assert truncate_on_word("abcde", 5) == "abcde"


# ─── empties ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw", ["", None, "   ", "<div></div>", "```\ncode\n```"])
def test_content_with_nothing_to_show_yields_empty_string(raw: str | None) -> None:
    """Never None: the column is nullable but the function is not the place to
    introduce one, and callers render this straight into a card."""
    assert to_excerpt(raw) == ""


# ─── determinism ────────────────────────────────────────────────────────────


def test_is_pure() -> None:
    """The point of dropping the LLM summarizer. Same input, same output, every
    run — an excerpt can never invent something the source did not say."""
    raw = "<p>Ship it 🚀 **today** — see [docs](http://x.com)</p>" + "word " * 200
    assert to_excerpt(raw) == to_excerpt(raw)
