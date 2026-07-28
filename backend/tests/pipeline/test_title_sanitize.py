"""LLM output cleanup + validation for titles and summaries.

Fixtures marked "prod" are real corrupted values pulled from the production
`article` table — the failure modes the pipeline actually produces.
"""

import pytest

from pipeline.llm_text import (
    is_corrupted,
    is_valid_title,
    sanitize_llm_text,
    strip_title_wrappers,
)


def clean_title(raw: str) -> str:
    """The exact chain _improve_titles applies before validating."""
    return strip_title_wrappers(sanitize_llm_text(raw))


# ─── sanitize_llm_text ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # prod: whole value wrapped in markdown bold
        (
            "**Cisco Agent Runtime SDK Integrates Policy**",
            "Cisco Agent Runtime SDK Integrates Policy",
        ),
        ("*Single asterisk emphasis*", "Single asterisk emphasis"),
        ("`Backtick wrapped`", "Backtick wrapped"),
        # prod: markdown copied out of a README mid-sentence
        (
            "Meta shares details on **Watermelon**, a framework.",
            "Meta shares details on Watermelon, a framework.",
        ),
        # unicode normalization (pre-existing, must not regress)
        ("“Smart quotes”", '"Smart quotes"'),
        ("a → b", "a -> b"),
        ("em—dash", "em-dash"),
        ("bullet • point", "bullet - point"),
        ("emoji 🚀 gone", "emoji  gone".replace("  ", " ")),
    ],
)
def test_sanitize_llm_text(raw: str, expected: str) -> None:
    assert sanitize_llm_text(raw) == expected


def test_sanitize_preserves_single_underscore() -> None:
    """Identifiers like snake_case must survive; only markdown __bold__ goes."""
    assert (
        sanitize_llm_text("Use the max_tokens parameter")
        == "Use the max_tokens parameter"
    )


def test_sanitize_keeps_newlines() -> None:
    """Summaries are multi-line by design."""
    assert sanitize_llm_text("line one\nline two") == "line one\nline two"


# ─── strip_title_wrappers ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("[HN] Anthropic ships a thing", "Anthropic ships a thing"),
        ("1. Anthropic ships a thing", "Anthropic ships a thing"),
        ('"Anthropic ships a thing"', "Anthropic ships a thing"),
        # prod: truncated generation leaves an unbalanced leading quote
        ('"Unclosed quote on a longer title', "Unclosed quote on a longer title"),
        # wrappers nest in arbitrary order
        ('"[HN] Anthropic ships a thing"', "Anthropic ships a thing"),
    ],
)
def test_strip_title_wrappers(raw: str, expected: str) -> None:
    assert strip_title_wrappers(raw) == expected


def test_strip_preserves_internal_punctuation() -> None:
    title = "DeepSeek-V4-Flash GGUF Quantizations with Llama.cpp Checkpoint Fix (611)"
    assert strip_title_wrappers(title) == title


# ─── is_corrupted (shared by titles and summaries) ──────────────────────────


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("Meta Unveils Watermelon:可能关联的内部GPT-5.5模型实验框架到", "han script"),
        ("伊律(Meagle) this highlights durable workflows", "han script mid-sentence"),
        ("Anthropic выпускает новую модель", "cyrillic"),
        ("Anthropic releases モデル today", "katakana"),
        ("Build Week bridges GPT-5.6 challenges\n }\n]", "json envelope leak"),
        ('Some title here" : "url', "json key/value fragment"),
        ("Title with a stray brace } in it", "json artifact"),
        ('{"title": "Anthropic ships a thing"}', "raw json object"),
    ],
)
def test_is_corrupted_detects(text: str, why: str) -> None:
    assert is_corrupted(text) is True, f"should flag: {why}"


@pytest.mark.parametrize(
    "text",
    [
        "vLLM integrates Hugging Face Transformers for production inference",
        "DeepSeek-V4-Flash GGUF Quantizations with Llama.cpp Checkpoint Fix (611)",
        "Mistral's Café Model Ships With Extended Context",
        "Meta ships a model.\nIt is free on Instagram.\nAPI access is included.",
    ],
)
def test_is_corrupted_allows_clean_text(text: str) -> None:
    assert is_corrupted(text) is False


# ─── is_valid_title ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("title", "why"),
    [
        ("", "empty"),
        ("   ", "whitespace only"),
        ("GPT-5.6", "too few words - truncated generation"),
        ("- . !", "no letters"),
        ("word " * 30, "too many words"),
        ("x" * 250, "too long"),
        ("A title\nwith a newline", "titles are single-line"),
        ("Meta Unveils Watermelon:可能关联的内部GPT-5.5模型实验框架到", "corrupted"),
        ("Read more at https://example.com/article-page", "contains url"),
    ],
)
def test_is_valid_title_rejects(title: str, why: str) -> None:
    assert is_valid_title(title) is False, f"should reject: {why}"


@pytest.mark.parametrize(
    "title",
    [
        "vLLM integrates Hugging Face Transformers for production-grade inference",
        "Target Leakage Inducing False NDCG Improvements in Recommendation Systems",
        "DeepSeek-V4-Flash GGUF Quantizations with Llama.cpp Checkpoint Fix (611)",
        "Anthropic Retires IP Tracker Code After Reinforcing Privacy Commitments",
        "Mistral's Café Model Ships With Extended Context",
        "Claude 4 ships",  # exactly at the word floor
    ],
)
def test_is_valid_title_accepts(title: str) -> None:
    assert is_valid_title(title) is True


# ─── full chains ────────────────────────────────────────────────────────────


def test_bold_wrapped_title_is_recovered_not_rejected() -> None:
    """The common case: strip the markdown and the title underneath is good."""
    raw = "**GPT-5.6 Enables Autonomous, Multi-Hour Agent Workflows Over Model Benchmarks**"
    cleaned = clean_title(raw)
    assert cleaned == (
        "GPT-5.6 Enables Autonomous, Multi-Hour Agent Workflows Over Model Benchmarks"
    )
    assert is_valid_title(cleaned)


def test_nested_wrappers_are_peeled() -> None:
    assert (
        clean_title('**"[HN] Anthropic ships a thing"**') == "Anthropic ships a thing"
    )


@pytest.mark.parametrize(
    "raw",
    [
        '**"GPT-5.6',  # truncated
        "Event highlights: Build Week bridges GPT-5.6 challenges\n }\n]",  # json leak
        "Meta Unveils Watermelon:可能关联的内部GPT-5.5模型实验框架到",  # cjk
    ],
)
def test_unrecoverable_title_garbage_fails_validation(raw: str) -> None:
    """Cleanup cannot save these — the gate must reject so the caller keeps the
    original title rather than overwriting it with garbage."""
    assert is_valid_title(clean_title(raw)) is False


def test_clean_title_survives_full_chain_unchanged() -> None:
    title = "Anthropic Retires IP Tracker Code After Reinforcing Privacy Commitments"
    assert clean_title(title) == title
    assert is_valid_title(clean_title(title))
