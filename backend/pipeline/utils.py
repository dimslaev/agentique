from datetime import UTC, datetime

import regex


def log(message: str) -> None:
    ts = datetime.now(UTC).isoformat()
    print(f"[{ts}] {message}")


def wait_ms(ms: int) -> None:
    import time

    time.sleep(ms / 1000)


# ─── LLM output cleanup ─────────────────────────────────────────────────────
#
# Two steps, applied to every LLM-authored field:
#
#   sanitize_llm_text()  - fix what's fixable (unicode, markdown, whitespace)
#   is_corrupted()       - detect what isn't (language drift, JSON leakage)
#
# Callers reject on is_corrupted() rather than trying to clean it: a model that
# emits Chinese mid-sentence or leaks its output envelope has produced garbage,
# not lightly-dirty text.


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


# Scripts that have no business in English-language AI news. A model drifting
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

MIN_TITLE_WORDS = 3
MAX_TITLE_WORDS = 20
MAX_TITLE_CHARS = 200


def strip_title_wrappers(text: str) -> str:
    """Remove title echo artifacts: [Source] tags, list numbering, wrapping quotes.

    Wrappers nest in arbitrary order (`"[HN] title"`), so peel to a fixed point.
    Run after sanitize_llm_text, which has already removed markdown.
    """
    s = text.strip()
    for _ in range(3):
        peeled = regex.sub(r"^\[[^\]]+\]\s*", "", s)
        peeled = regex.sub(r"^\d+\.\s*", "", peeled)
        # Leading and trailing handled independently: a truncated generation
        # leaves an unbalanced quote behind.
        peeled = regex.sub(r"^[\"']\s*|\s*[\"']$", "", peeled).strip()
        if peeled == s:
            break
        s = peeled
    return s


def is_valid_title(text: str) -> bool:
    """Gate an LLM-rewritten title. False means the caller keeps the original."""
    s = text.strip()
    if not s or "\n" in s or "\r" in s:
        return False
    if len(s) > MAX_TITLE_CHARS or is_corrupted(s):
        return False
    if regex.search(r"https?://", s) or not regex.search(r"\p{L}", s):
        return False
    return MIN_TITLE_WORDS <= len(s.split()) <= MAX_TITLE_WORDS


# ─── Summaries ──────────────────────────────────────────────────────────────

MIN_SUMMARY_WORDS = 5
MAX_SUMMARY_CHARS = 1000


def is_valid_summary(text: str) -> bool:
    """Gate an LLM summary. False means store no summary at all.

    Unlike a title there is no original to fall back to, so the choice is a
    clean summary or none — never a corrupted one.
    """
    s = text.strip()
    if not s or len(s) > MAX_SUMMARY_CHARS or is_corrupted(s):
        return False
    if not regex.search(r"\p{L}", s):
        return False
    return len(s.split()) >= MIN_SUMMARY_WORDS
