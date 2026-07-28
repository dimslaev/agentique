"""Turn raw article content into the short blurb shown on a card.

This replaced an LLM summarization pass. The summarizer cost one call per
article and was the pipeline's most reliable source of corruption — it echoed
the markdown of the READMEs it was fed, leaked CJK from multilingual sources,
and occasionally emitted its own JSON envelope, all of which then got copied
into titles by the title-rewriter. Three regression tests existed solely to
pin failure modes it kept re-finding.

An excerpt is not as good as a summary. It is the article's opening rather than
its point. But it is free, deterministic, and cannot invent anything the source
did not say — and the failure mode of a bad excerpt (a truncated sentence) is
visibly worse-looking rather than subtly wrong.

Source content is markdown, HTML, or a mix, straight from a feed. The order of
operations below matters: code and tag stripping must happen before entity
decoding, or an escaped `&lt;div&gt;` in a code sample re-enters as markup.
"""

from __future__ import annotations

import html

import regex

from pipeline.llm_text import sanitize_llm_text

# Characters of article text on a card. The feed and the homepage lanes both
# clamp to three lines; this is roughly what fits without the clamp doing the
# truncating, so the ellipsis is honest about there being more.
EXCERPT_CHARS = 280

# Fenced and indented code, plus the two HTML elements whose *content* is not
# text. Removed wholesale rather than tag-stripped: the body is noise either way.
_CODE_FENCE = regex.compile(r"```.*?```|~~~.*?~~~", regex.DOTALL)
_SCRIPT_STYLE = regex.compile(
    r"<(script|style|noscript|svg)\b[^>]*>.*?</\1>", regex.DOTALL | regex.IGNORECASE
)
_HTML_COMMENT = regex.compile(r"<!--.*?-->", regex.DOTALL)
_TAG = regex.compile(r"<[^>]+>")

# Markdown that carries no text worth keeping.
_MD_IMAGE = regex.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = regex.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_REF_DEF = regex.compile(r"^\s*\[[^\]]+\]:\s*\S+.*$", regex.MULTILINE)
_MD_HEADING = regex.compile(r"^\s{0,3}#{1,6}\s*", regex.MULTILINE)
_MD_QUOTE = regex.compile(r"^\s{0,3}>+\s?", regex.MULTILINE)
_MD_RULE = regex.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$", regex.MULTILINE)
_MD_LIST = regex.compile(r"^\s{0,3}([-+*]|\d+[.)])\s+", regex.MULTILINE)
_MD_TABLE_DIVIDER = regex.compile(r"^\s*\|?[\s:|-]{4,}\|?\s*$", regex.MULTILINE)
# Only pipes on a line that actually looks like a table row are separators;
# a lone `|` in prose is usually "a | b" meaning "or" and is left alone.
_MD_TABLE_ROW = regex.compile(r"^[ \t]*\|.*\|[ \t]*$", regex.MULTILINE)

# Two classes of leftover that survive markup stripping and are pure noise on a
# card. Measured on the prod dump: box-drawing and block characters (290
# occurrences) are the ASCII-art banner at the top of a README; zero-width
# characters are invisible but break copy-paste and substring search.
#
# Deliberately NOT stripped: CJK. The old summarizer treated it as corruption
# because the model was drifting out of English, but an excerpt only ever
# repeats the source — a Chinese article should read as Chinese.
_BOX_DRAWING = regex.compile(r"[\u2500-\u259F]+")
_ZERO_WIDTH = regex.compile(r"[\u200B-\u200D\u2060\uFEFF]")

_WHITESPACE = regex.compile(r"\s+")
# Punctuation left dangling by a word-boundary cut.
_TRAILING_PUNCT = regex.compile(r"[\s,;:.\-–—/|(\[{&]+$")

ELLIPSIS = "..."


def _strip_markup(text: str) -> str:
    s = _CODE_FENCE.sub(" ", text)
    s = _SCRIPT_STYLE.sub(" ", s)
    s = _HTML_COMMENT.sub(" ", s)
    s = _TAG.sub(" ", s)
    # Decode only after the first tag pass, then strip again: feeds routinely
    # ship `&lt;p&gt;`-escaped markup that would otherwise survive as visible
    # angle brackets.
    s = html.unescape(s)
    s = _TAG.sub(" ", s)

    s = _MD_REF_DEF.sub(" ", s)
    s = _MD_IMAGE.sub(" ", s)
    s = _MD_LINK.sub(r"\1", s)
    s = _MD_RULE.sub(" ", s)
    s = _MD_TABLE_DIVIDER.sub(" ", s)
    s = _MD_TABLE_ROW.sub(lambda m: m.group(0).replace("|", " "), s)
    s = _MD_HEADING.sub("", s)
    s = _MD_QUOTE.sub("", s)
    s = _MD_LIST.sub("", s)
    return s


def truncate_on_word(text: str, limit: int) -> str:
    """Cut to at most ``limit`` characters without splitting a word.

    The ellipsis is part of the budget, so the result never exceeds ``limit``.
    A single word longer than the limit is cut mid-word rather than returning
    nothing — that is a URL or a hash, and losing the excerpt entirely would be
    worse than an ugly one.
    """
    if len(text) <= limit:
        return text
    if limit <= len(ELLIPSIS):
        return text[:limit]

    budget = limit - len(ELLIPSIS)
    head = text[:budget]
    cut = head.rfind(" ")
    if cut > 0:
        head = head[:cut]
    return _TRAILING_PUNCT.sub("", head) + ELLIPSIS


def to_excerpt(content: str | None, limit: int = EXCERPT_CHARS) -> str:
    """A card-sized, plain-text opening of the article. Never None; may be "".

    Emoji, markup and entities are gone, whitespace is collapsed to single
    spaces, and the result is trimmed on a word boundary. Pure — no I/O, no
    model, same input always gives the same output.
    """
    if not content:
        return ""
    s = _strip_markup(content)
    # Handles emoji, smart quotes, arrows, dashes and markdown emphasis. Shared
    # with the title path so both are normalized the same way. Runs before the
    # zero-width strip so emoji ZWJ sequences are matched whole.
    s = sanitize_llm_text(s)
    s = _BOX_DRAWING.sub(" ", s)
    s = _ZERO_WIDTH.sub("", s)
    s = _WHITESPACE.sub(" ", s).strip()
    return truncate_on_word(s, limit)
