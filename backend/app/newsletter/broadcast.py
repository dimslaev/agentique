"""The weekly issue: one short essay, rendered into one template and drafted as
a Resend broadcast.

The newsletter agent writes prose, never HTML. The body is plain text with
three marks: a blank line between paragraphs, `- ` at the start of a list line,
and `[text](url)` for a link (plus backticks for code). This module escapes
everything else, so nothing the agent writes can break the layout, and renders
it into `weekly_issue.html` and a plain-text twin.

The agent drafts three a week, one per topic, and a person reads them and sends
one from the Resend dashboard. Nothing here sends, and nothing is stored:
Resend keeps every broadcast, drafted and sent.
"""

from __future__ import annotations

import re
from datetime import date
from typing import TypedDict

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from app.platform.email import TEMPLATES
from app.platform.logging import log
from app.platform.settings import settings

# Resend swaps this for each recipient's own unsubscribe link.
UNSUBSCRIBE_PLACEHOLDER = "{{{RESEND_UNSUBSCRIBE_URL}}}"

MAX_SUBJECT = 90
MAX_LABEL = 60
# One to two minutes of reading.
MIN_WORDS = 150
MAX_WORDS = 600
# An issue explains a thing through what people wrote about it; fewer links
# than this and it is an opinion piece.
MIN_LINKS = 3

# The site's colours (frontend/src/index.css): --signal for links, --paper
# for text on --ink.
LINK_STYLE = "color:#b8410f;text-decoration:underline;"
CODE_STYLE = (
    "font-family:'IBM Plex Mono',ui-monospace,Menlo,Consolas,monospace;"
    "font-size:14px;background-color:#ebe8dc;padding:1px 4px;border-radius:3px;"
)

_INLINE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)|`([^`\n]+)`")
_WORD = re.compile(r"\S+")

_templates = Environment(
    loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"])
)


class IssueError(ValueError):
    """An issue that cannot be drafted as given, returned as a message."""


class Issue(TypedDict):
    # Which draft this is, for telling three apart in Resend: the topic.
    label: str
    subject: str
    # The line an inbox shows after the subject.
    preheader: str
    body: str


class Block(TypedDict):
    # "p" or "ul".
    kind: str
    lines: list[str]


def blocks(body: str) -> list[Block]:
    """Paragraphs and lists, split on blank lines. A block whose every line
    starts with "- " is a list; any other block is one paragraph. Pure."""
    out: list[Block] = []
    for chunk in body.split("\n\n"):
        lines = [line.strip() for line in chunk.strip().splitlines() if line.strip()]
        if not lines:
            continue
        if all(line.startswith("- ") for line in lines):
            out.append({"kind": "ul", "lines": [line[2:].strip() for line in lines]})
        else:
            out.append({"kind": "p", "lines": [" ".join(lines)]})
    return out


def links(body: str) -> list[str]:
    return [m.group(2) for m in _INLINE.finditer(body) if m.group(2) is not None]


def inline_html(text: str) -> Markup:
    """Escape ``text`` and turn its links and code spans into tags. Pure."""
    out: list[Markup] = []
    pos = 0
    for m in _INLINE.finditer(text):
        out.append(escape(text[pos : m.start()]))
        if m.group(2) is not None:
            out.append(
                Markup('<a href="{}" style="{}">{}</a>').format(
                    m.group(2), LINK_STYLE, m.group(1)
                )
            )
        else:
            out.append(
                Markup('<code style="{}">{}</code>').format(CODE_STYLE, m.group(3))
            )
        pos = m.end()
    out.append(escape(text[pos:]))
    return Markup("").join(out)


def inline_text(text: str) -> str:
    """The same line for a plain-text client: "text (url)", code unmarked. Pure."""
    return _INLINE.sub(
        lambda m: f"{m.group(1)} ({m.group(2)})" if m.group(2) else m.group(3), text
    )


def word_count(body: str) -> int:
    return len(_WORD.findall(_INLINE.sub(lambda m: m.group(1) or m.group(3), body)))


def validate(issue: Issue) -> None:
    """Refuse an issue a reader should not get. Pure."""
    subject = issue["subject"].strip()
    if not subject or len(subject) > MAX_SUBJECT:
        raise IssueError(f"The subject must be 1-{MAX_SUBJECT} characters.")
    label = issue["label"].strip()
    if not label or len(label) > MAX_LABEL:
        raise IssueError(f"The label must be 1-{MAX_LABEL} characters.")
    words = word_count(issue["body"])
    if not MIN_WORDS <= words <= MAX_WORDS:
        raise IssueError(
            f"The body is {words} words; an issue is {MIN_WORDS}-{MAX_WORDS}, "
            "one to two minutes of reading."
        )
    urls = links(issue["body"])
    for url in urls:
        if not url.startswith(("https://", "http://")):
            raise IssueError(f"Link with no http(s) URL: {url!r}")
    if len(set(urls)) < MIN_LINKS:
        raise IssueError(
            f"The body links {len(set(urls))} sources; link at least {MIN_LINKS} "
            "as [text](url)."
        )


def render_html(issue: Issue) -> str:
    return _templates.get_template("weekly_issue.html").render(
        subject=issue["subject"],
        preheader=issue["preheader"],
        blocks=[
            {"kind": b["kind"], "lines": [inline_html(line) for line in b["lines"]]}
            for b in blocks(issue["body"])
        ],
        site_url=settings.FRONTEND_HOST.rstrip("/"),
        unsubscribe_url=UNSUBSCRIBE_PLACEHOLDER,
    )


def render_text(issue: Issue) -> str:
    """The plain-text twin, for clients that do not show HTML. Pure."""
    out: list[str] = []
    for b in blocks(issue["body"]):
        lines = [inline_text(line) for line in b["lines"]]
        out.append(
            "\n".join(f"- {line}" for line in lines) if b["kind"] == "ul" else lines[0]
        )
    site = settings.FRONTEND_HOST.rstrip("/")
    out.append(f"The feed: {site}/feed\nUnsubscribe: {UNSUBSCRIBE_PLACEHOLDER}")
    return "\n\n".join(out)


def _sender() -> str:
    missing = [
        name
        for name, value in (
            ("RESEND_API_KEY", settings.RESEND_API_KEY),
            ("RESEND_AUDIENCE_ID", settings.RESEND_AUDIENCE_ID),
            ("EMAILS_FROM_EMAIL", settings.EMAILS_FROM_EMAIL),
        )
        if not value
    ]
    if missing:
        raise IssueError(f"Resend is not configured: {', '.join(missing)} unset.")
    resend.api_key = settings.RESEND_API_KEY
    return f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"


def draft(issue: Issue, issue_date: date | None = None) -> str:
    """Create the issue as a draft broadcast. Returns the line the agent
    reports, the broadcast id first. Sending is a person's, from the Resend
    dashboard."""
    validate(issue)
    sender = _sender()
    issue_date = issue_date or date.today()
    label = issue["label"].strip()
    created = resend.Broadcasts.create(
        {
            "audience_id": settings.RESEND_AUDIENCE_ID or "",
            "from": sender,
            "subject": issue["subject"].strip(),
            "html": render_html(issue),
            "text": render_text(issue),
            "name": f"Weekly {issue_date.isoformat()} · {label}",
        }
    )
    log(f"  Drafted weekly issue {label!r} as broadcast {created['id']}")
    return f"Drafted broadcast {created['id']} ({label})."
