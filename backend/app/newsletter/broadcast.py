"""The weekly issue: one short essay, rendered into one template and drafted as
a Resend broadcast, and saved by the agent as a blog post.

The newsletter agent writes prose, never HTML. An issue is the text of a blog
post file (`frontend/content/blog/<date>-<slug>.md`): a frontmatter block with
`title`, `description` and `topic`, then a body in plain text with three marks:
a blank line between paragraphs, `- ` at the start of a list line, and
`[text](url)` for a link (plus backticks for code). This module escapes
everything else, so nothing the agent writes can break the layout, and renders
it into `weekly_issue.html` and a plain-text twin.

The content rules for an issue live here and nowhere else; the blog build only
checks what a page needs to render. The agent drafts three a week, one per
topic, and a person reads them and sends one from the Resend dashboard. Nothing
here sends, and nothing is stored: the posts live in git, the broadcasts in
Resend.
"""

from __future__ import annotations

import json
import re
import unicodedata
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

# The page's <title> appends " · agentique"; this keeps it within the ~65
# characters a search result shows, and fits an inbox subject line.
MAX_TITLE = 55
MAX_DESCRIPTION = 160
MAX_SLUG = 60
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
_TOPIC = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_FIELD = re.compile(r"^([a-z]+):(?:\s+(.*))?$")
# Plain YAML scalars that YAML would read as something else, or fail on. The
# blog build parses the same frontmatter with a YAML parser.
_UNSAFE_PLAIN = re.compile(r"^[-?:,\[\]{}#&*!|>'\"%@`]|: | #|:$")
FIELDS = ("title", "description", "topic")

_templates = Environment(
    loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"])
)


class IssueError(ValueError):
    """An issue that cannot be drafted as given, returned as a message."""


class Issue(TypedDict):
    # The email's subject and the post's headline.
    title: str
    # The line an inbox shows after the subject, and the post's lede.
    description: str
    # A kebab slug; names the draft in Resend, for telling three apart.
    topic: str
    body: str


def _scalar(key: str, raw: str) -> str:
    """One frontmatter value: plain, "double" or 'single' quoted, as YAML
    reads it."""
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            raise IssueError(f"The {key} is not a valid double-quoted string.")
        if not isinstance(value, str):
            raise IssueError(f"The {key} is not a valid double-quoted string.")
        return value
    if raw.startswith("'"):
        if len(raw) < 2 or not raw.endswith("'") or "'" in raw[1:-1].replace("''", ""):
            raise IssueError(f"The {key} is not a valid single-quoted string.")
        return raw[1:-1].replace("''", "'")
    if _UNSAFE_PLAIN.search(raw):
        raise IssueError(f'Quote the {key} in double quotes: {key}: "..."')
    return raw


def parse(post: str) -> Issue:
    """Read a post file's text: `---`, one `key: value` line for each of
    title, description and topic, `---`, then the body. Pure."""
    text = post.replace("\r\n", "\n").lstrip("\ufeff")
    if not text.startswith("---\n"):
        raise IssueError("The post must start with a --- frontmatter line.")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise IssueError("The frontmatter is not closed with a --- line.")
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        m = _FIELD.match(line)
        if not m:
            raise IssueError(f"Frontmatter line is not `key: value`: {line!r}")
        key, raw = m.group(1), (m.group(2) or "").strip()
        if key not in FIELDS:
            raise IssueError(
                f"Unknown frontmatter key {key!r}; a post has only "
                f"{', '.join(FIELDS)}. Date and slug come from the filename."
            )
        if key in fields:
            raise IssueError(f"The frontmatter sets {key} twice.")
        fields[key] = _scalar(key, raw).strip()
    return {
        "title": fields.get("title", ""),
        "description": fields.get("description", ""),
        "topic": fields.get("topic", ""),
        "body": text[end + 5 :].strip(),
    }


def slugify(title: str) -> str:
    """The post's slug: lowercase ascii, every run of anything else one "-",
    cut on a word boundary. Pure."""
    ascii_title = (
        unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    if len(slug) > MAX_SLUG:
        cut = slug[: MAX_SLUG + 1]
        slug = cut[: cut.rfind("-")] if "-" in cut else slug[:MAX_SLUG]
    return slug


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
    title = issue["title"].strip()
    if not title or len(title) > MAX_TITLE:
        raise IssueError(
            f"The title is {len(title)} characters; it must be 1-{MAX_TITLE}."
        )
    if not slugify(title):
        raise IssueError("The title has no letters or digits to make a slug from.")
    description = issue["description"].strip()
    if not description or len(description) > MAX_DESCRIPTION:
        raise IssueError(
            f"The description is {len(description)} characters; it must be "
            f"1-{MAX_DESCRIPTION}."
        )
    if not _TOPIC.match(issue["topic"]):
        raise IssueError(
            f"The topic {issue['topic']!r} must be a kebab slug, like local-ai."
        )
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
        subject=issue["title"].strip(),
        preheader=issue["description"].strip(),
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


def post_path(issue: Issue, issue_date: date) -> str:
    """Where the agent saves the post, relative to the repo root. Pure."""
    return (
        f"frontend/content/blog/{issue_date.isoformat()}-{slugify(issue['title'])}.md"
    )


def draft(post: str, issue_date: date | None = None) -> str:
    """Create the post as a draft broadcast. Returns the line the agent
    reports, the broadcast id first, and the path to save the post at.
    Sending is a person's, from the Resend dashboard."""
    issue = parse(post)
    validate(issue)
    sender = _sender()
    issue_date = issue_date or date.today()
    topic = issue["topic"]
    created = resend.Broadcasts.create(
        {
            "audience_id": settings.RESEND_AUDIENCE_ID or "",
            "from": sender,
            "subject": issue["title"].strip(),
            "html": render_html(issue),
            "text": render_text(issue),
            "name": f"Weekly {issue_date.isoformat()} · {topic}",
        }
    )
    log(f"  Drafted weekly issue {topic!r} as broadcast {created['id']}")
    return (
        f"Drafted broadcast {created['id']} ({topic}). "
        f"Save the post, exactly as passed, at {post_path(issue, issue_date)}"
    )
