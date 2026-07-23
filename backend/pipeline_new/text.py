"""Sanitize and validate every LLM-authored field before it reaches the DB.

Two moves, applied to titles and summaries alike:

  sanitize()     - fix what is fixable (unicode, markdown, whitespace)
  is_corrupted() - detect what is not (language drift, JSON-envelope leakage)

Callers reject on ``is_corrupted`` rather than trying to clean it: a model that
emits CJK mid-sentence or leaks its output envelope has produced garbage, not
lightly-dirty text. A summary has no fallback, so the choice is a clean summary
or none; a title falls back to the feed's own (already trustworthy) title.
"""

from __future__ import annotations

import regex


def sanitize(text: str) -> str:
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


# Scripts that have no business in English-language AI news — a model drifting
# out of English is not recoverable by cleanup.
_NON_LATIN = regex.compile(
    r"[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}"
    r"\p{Script=Hangul}\p{Script=Cyrillic}\p{Script=Arabic}\p{Script=Hebrew}]"
)
# Braces, brackets, or a quoted key/value mean the structured-output envelope
# leaked into the field.
_JSON_ARTIFACT = regex.compile(r"[{}\[\]]|\"\s*:\s*\"")


def is_corrupted(text: str) -> bool:
    """True if the text shows a failure mode cleanup cannot fix."""
    return bool(_NON_LATIN.search(text) or _JSON_ARTIFACT.search(text))


# ─── Titles ─────────────────────────────────────────────────────────────────

MIN_TITLE_CHARS = 4
MAX_TITLE_CHARS = 300


def clean_title(raw: str) -> str:
    """Feed titles are editorial and trustworthy, so they are sanitized rather
    than rewritten: collapse whitespace/newlines, normalize unicode, unwrap a
    stray leading/trailing quote. Returns "" if nothing usable is left."""
    s = sanitize(regex.sub(r"\s+", " ", raw))
    s = regex.sub(r"^[\"']\s*|\s*[\"']$", "", s).strip()
    if len(s) < MIN_TITLE_CHARS or len(s) > MAX_TITLE_CHARS:
        return ""
    return s


# ─── Summaries ──────────────────────────────────────────────────────────────

MIN_SUMMARY_WORDS = 5
MAX_SUMMARY_CHARS = 1000


def clean_summary(raw: str | None) -> str:
    """Sanitize an LLM summary and gate it. Returns "" (store no summary) if it
    is empty, corrupted, out of bounds, or has no real words — never a garbled
    one, since there is nothing to fall back to."""
    if not raw:
        return ""
    s = sanitize(raw)
    if not s or len(s) > MAX_SUMMARY_CHARS or is_corrupted(s):
        return ""
    if not regex.search(r"\p{L}", s):
        return ""
    if len(s.split()) < MIN_SUMMARY_WORDS:
        return ""
    return s
