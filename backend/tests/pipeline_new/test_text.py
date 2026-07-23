"""Sanitize + gate for the RSS pipeline's LLM-authored fields.

The failure modes are the ones the old pipeline actually shipped to prod:
markdown echoed from a README, language drift, and JSON-envelope leakage.
"""

from __future__ import annotations

import pytest

from pipeline_new.text import clean_summary, clean_title, is_corrupted, sanitize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("**Bold wrapped**", "Bold wrapped"),
        ("*Single asterisk*", "Single asterisk"),
        ("`Backtick wrapped`", "Backtick wrapped"),
        ("“Smart quotes”", '"Smart quotes"'),
        ("a → b", "a -> b"),
        ("em—dash", "em-dash"),
        ("bullet • point", "bullet - point"),
    ],
)
def test_sanitize(raw: str, expected: str) -> None:
    assert sanitize(raw) == expected


def test_sanitize_preserves_snake_case() -> None:
    assert sanitize("Use the max_tokens parameter") == "Use the max_tokens parameter"


@pytest.mark.parametrize(
    "text",
    [
        "伊律(Meagle) durable workflows",  # han
        "Anthropic выпускает модель",  # cyrillic
        "Build Week challenges\n }\n]",  # json leak
        'Some title" : "url',  # json key/value
    ],
)
def test_is_corrupted_flags(text: str) -> None:
    assert is_corrupted(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "vLLM integrates Hugging Face Transformers for production inference",
        "Mistral's Café Model Ships With Extended Context",
    ],
)
def test_is_corrupted_allows_clean(text: str) -> None:
    assert is_corrupted(text) is False


# ─── clean_title ─────────────────────────────────────────────────────────────


def test_clean_title_collapses_whitespace_and_newlines() -> None:
    assert clean_title("Anthropic\n  ships   Claude 4") == "Anthropic ships Claude 4"


def test_clean_title_unwraps_stray_quotes() -> None:
    assert clean_title('"Anthropic ships Claude 4"') == "Anthropic ships Claude 4"


def test_clean_title_strips_markdown() -> None:
    assert clean_title("**Anthropic ships Claude 4**") == "Anthropic ships Claude 4"


@pytest.mark.parametrize("raw", ["", "   ", "ab"])
def test_clean_title_rejects_too_short(raw: str) -> None:
    assert clean_title(raw) == ""


def test_clean_title_rejects_too_long() -> None:
    assert clean_title("word " * 100) == ""


# ─── clean_summary ───────────────────────────────────────────────────────────


def test_clean_summary_recovers_markdown() -> None:
    raw = "Meta shares details on **Watermelon**.\nIt tests `scalability` of models."
    out = clean_summary(raw)
    assert "**" not in out and "`" not in out
    assert out.startswith("Meta shares details")


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "Too short.",
        "x" * 1200,
        "Meta shares details.\n这是一个内部实验框架。",  # cjk drift
        'Some summary" : "value',  # json fragment
    ],
)
def test_clean_summary_rejects(raw: str | None) -> None:
    assert clean_summary(raw) == ""


def test_clean_summary_keeps_multiline() -> None:
    s = "Line one is here now.\nLine two is here now.\nLine three is here now."
    assert clean_summary(s) == s
