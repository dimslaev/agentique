"""Normalising an enum-typed BAML field to a plain string, and cleaning
model-authored text before it is stored.

Fixtures marked "prod" are real corrupted values pulled from the production
`article` table, the failure modes the pipeline actually produces.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from app.core.llm_text import enum_value, sanitize_llm_text


class _Colour(StrEnum):
    red = "red"


def test_enum_value_unwraps_an_enum() -> None:
    assert enum_value(_Colour.red) == "red"


def test_enum_value_passes_a_plain_string_through() -> None:
    """BAML returns plain strings for some fields and enum members for others,
    and which one has changed across regenerations."""
    assert enum_value("red") == "red"


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
    """sanitize_llm_text is content-agnostic; newline stripping is the caller's job."""
    assert sanitize_llm_text("line one\nline two") == "line one\nline two"
