"""The `draft_issue` tool: one weekly issue as a Resend broadcast draft.

Behind the write scope because a draft lands in the audience subscribers are
mailed from. Sending is a person's, from the Resend dashboard.
"""

from __future__ import annotations

from fastmcp.exceptions import ToolError

from app.entry.mcp.auth import require_write
from app.features.newsletter import service as newsletter
from app.features.newsletter.model import IssueError


def draft_issue(post: str) -> str:
    """Draft one weekly issue as a Resend broadcast.

    `post` is the whole blog post file: a frontmatter block, then the body.

        ---
        title: What does Ollama's MLX backend actually do?
        description: One line that makes someone open it.
        topic: local-ai
        ---
        The essay...

    `title` (1-55 characters) is the subject and the post's headline,
    `description` (1-160) the line an inbox shows after it, `topic` a kebab
    slug that names the draft in Resend. Quote a value in double quotes if it
    holds ": " or starts with a quote or a symbol. The body is plain text,
    150-600 words: a blank line between paragraphs, `- ` to start a list line,
    `[text](url)` for a link (at least 3 distinct sources), backticks for code.
    The server renders it into the site's template. Returns the broadcast id
    and the path to save the post at, exactly as passed. Nothing is sent: a
    person reads the drafts and sends one from the Resend dashboard.
    """
    require_write()
    try:
        return newsletter.draft(post)
    except IssueError as exc:
        raise ToolError(str(exc))
