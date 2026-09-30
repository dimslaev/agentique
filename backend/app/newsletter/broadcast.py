"""The weekly issue: rendered into one template, drafted as a Resend broadcast.

The newsletter agent writes the words and picks the links; it never writes
HTML. It hands over a structured issue, this module renders it into
`weekly_issue.html` (autoescaped, so nothing the agent writes can break the
layout) and a plain-text twin, and creates a Resend broadcast to the audience
the signup route syncs subscribers to.

Nothing is stored here. Resend keeps every broadcast, drafted and sent, and an
issue covers exactly the week before it, so there is no history to consult.
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.platform.email import TEMPLATES
from app.platform.logging import log
from app.platform.settings import settings

# Resend swaps this for each recipient's own unsubscribe link, in a broadcast
# only. A preview is a plain email, so it gets the site instead.
UNSUBSCRIBE_PLACEHOLDER = "{{{RESEND_UNSUBSCRIBE_URL}}}"

MAX_SUBJECT = 120
MAX_STORIES = 6
MAX_FURTHER = 3
MAX_QUICK_HITS = 10

_templates = Environment(
    loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"])
)


class IssueError(ValueError):
    """An issue that cannot be drafted as given, returned as a message."""


class FurtherLink(TypedDict):
    title: str
    url: str
    # The writer or publisher, as a reader would name them.
    by: str
    # One line: what this adds to the story.
    note: str


class IssueStory(TypedDict):
    title: str
    url: str
    # Plain text; a blank line starts a new paragraph.
    body: str
    further: list[FurtherLink]


class QuickHit(TypedDict):
    title: str
    url: str
    line: str


class Issue(TypedDict):
    subject: str
    preheader: str
    intro: str
    stories: list[IssueStory]
    quick_hits: list[QuickHit]


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _check_url(url: str, what: str) -> None:
    if not url.startswith(("https://", "http://")):
        raise IssueError(f"{what} has no http(s) URL: {url!r}")


def validate(issue: Issue) -> None:
    """Refuse an issue a reader should not get. Pure."""
    subject = issue["subject"].strip()
    if not subject or len(subject) > MAX_SUBJECT:
        raise IssueError(f"The subject must be 1-{MAX_SUBJECT} characters.")
    if not issue["intro"].strip():
        raise IssueError("The intro is empty.")
    if not 1 <= len(issue["stories"]) <= MAX_STORIES:
        raise IssueError(f"An issue carries 1-{MAX_STORIES} stories.")
    if len(issue["quick_hits"]) > MAX_QUICK_HITS:
        raise IssueError(f"At most {MAX_QUICK_HITS} quick hits.")
    for story in issue["stories"]:
        _check_url(story["url"], f"Story {story['title']!r}")
        if not story["body"].strip():
            raise IssueError(f"Story {story['title']!r} has no body.")
        if len(story["further"]) > MAX_FURTHER:
            raise IssueError(
                f"Story {story['title']!r} has more than {MAX_FURTHER} go-further links."
            )
        for link in story["further"]:
            _check_url(link["url"], f"Go-further link {link['title']!r}")
    for hit in issue["quick_hits"]:
        _check_url(hit["url"], f"Quick hit {hit['title']!r}")


def render_html(issue: Issue, issue_date: date, unsubscribe_url: str) -> str:
    return _templates.get_template("weekly_issue.html").render(
        subject=issue["subject"],
        preheader=issue["preheader"],
        issue_date=f"{issue_date.day} {issue_date:%B %Y}",
        intro=_paragraphs(issue["intro"]),
        stories=[
            {**story, "paragraphs": _paragraphs(story["body"])}
            for story in issue["stories"]
        ],
        quick_hits=issue["quick_hits"],
        site_url=settings.FRONTEND_HOST.rstrip("/"),
        unsubscribe_url=unsubscribe_url,
    )


def render_text(issue: Issue, unsubscribe_url: str) -> str:
    """The plain-text twin, for clients that do not show HTML. Pure.

    Blocks are separated by a blank line: a paragraph, a story heading with its
    link, a list.
    """
    blocks = _paragraphs(issue["intro"])
    for story in issue["stories"]:
        blocks.append(f"{story['title']}\n{story['url']}")
        blocks += _paragraphs(story["body"])
        if story["further"]:
            links = [
                f"- {link['title']} ({link['by']})"
                + (f" - {link['note']}" if link["note"] else "")
                + f"\n  {link['url']}"
                for link in story["further"]
            ]
            blocks.append("\n".join(["Go further:", *links]))
    if issue["quick_hits"]:
        hits = [
            f"- {hit['title']} - {hit['line']}\n  {hit['url']}"
            for hit in issue["quick_hits"]
        ]
        blocks.append("\n".join(["Quick hits:", *hits]))
    blocks.append(f"Unsubscribe: {unsubscribe_url}")
    return "\n\n".join(blocks)


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
    """Create the issue as a draft broadcast and mail a preview. Returns what
    happened, the broadcast id first.

    Sending is a separate step (`send`), from here or the Resend dashboard. A
    failed preview is reported, not raised: the draft exists either way.
    """
    validate(issue)
    sender = _sender()
    issue_date = issue_date or date.today()
    created = resend.Broadcasts.create(
        {
            "audience_id": settings.RESEND_AUDIENCE_ID or "",
            "from": sender,
            "subject": issue["subject"].strip(),
            "html": render_html(issue, issue_date, UNSUBSCRIBE_PLACEHOLDER),
            "text": render_text(issue, UNSUBSCRIBE_PLACEHOLDER),
            "name": f"Weekly {issue_date.isoformat()}",
        }
    )
    broadcast_id = created["id"]
    log(f"  Drafted weekly issue as broadcast {broadcast_id}")

    preview_to = settings.NEWSLETTER_PREVIEW_EMAIL or settings.EMAILS_FROM_EMAIL
    site = settings.FRONTEND_HOST
    try:
        resend.Emails.send(
            {
                "from": sender,
                "to": str(preview_to),
                "subject": f"[Draft] {issue['subject'].strip()}",
                "html": render_html(issue, issue_date, site),
                "text": render_text(issue, site),
            }
        )
        preview = f"preview sent to {preview_to}"
    except Exception as exc:
        preview = f"preview failed: {exc}"
    return f"Drafted broadcast {broadcast_id}; {preview}."


def send(broadcast_id: str) -> str:
    """Send a drafted broadcast to every subscriber in the audience."""
    _sender()
    resend.Broadcasts.send({"broadcast_id": broadcast_id})
    log(f"  Sent weekly issue broadcast {broadcast_id}")
    return f"Sent broadcast {broadcast_id}."
