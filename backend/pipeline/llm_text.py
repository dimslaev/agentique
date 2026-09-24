"""Cleanup for model-authored text.

``sanitize_llm_text`` normalizes unicode, strips markdown and collapses
whitespace on what gets stored. ``enum_value`` reads a field BAML types as an
enum rather than as free text.
"""

from __future__ import annotations

from typing import Any

import regex


def enum_value(raw: Any) -> str:
    """The ``.value`` of an enum-ish object, else the object itself, as a str.

    BAML returns plain strings for some fields and enum members for others, and
    which one it is has changed across regenerations - callers tolerate both
    rather than depend on it.
    """
    return str(getattr(raw, "value", raw))


def sanitize_llm_text(text: str) -> str:
    """Normalize unicode, strip markdown, collapse whitespace."""
    s = text
    s = regex.sub(r"[‘’‚]", "'", s)
    s = regex.sub(r"[“”„]", '"', s)
    s = regex.sub(r"→", "->", s)
    s = regex.sub(r"←", "<-", s)
    s = regex.sub(r"↔", "<->", s)
    s = regex.sub(r"[–—]", "-", s)
    s = regex.sub(r"…", "...", s)
    s = regex.sub(r"[•‣◦▪▫]", "-", s)
    s = regex.sub(
        r"[\p{Emoji_Presentation}\p{Extended_Pictographic}]️?"
        r"(‍[\p{Emoji_Presentation}\p{Extended_Pictographic}]️?)*",
        "",
        s,
    )
    s = regex.sub(r"\*+|`+|_{2,}", "", s)  # markdown emphasis
    s = regex.sub(r"[ \t]{2,}", " ", s)
    return s.strip()
