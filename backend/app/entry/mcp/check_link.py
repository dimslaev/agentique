"""The `check_link` tool: the facts behind a repo or model URL."""

from __future__ import annotations

from fastmcp.exceptions import ToolError

from app.entry.mcp.auth import require_write
from app.features.curation import service as curation
from app.features.curation.model import LinkError


def check_link(url: str) -> dict[str, object]:
    """Look up a GitHub or GitLab repo, or a Hugging Face model or dataset.

    Repos: `stars`, `forks`, `last_push`, `license`, `archived`, `has_readme`,
    `description`. Models and datasets: `downloads`, `likes`, `last_modified`,
    `license`, `files` (count), and for a model `weights` (true when weight
    files are present). A value the lookup could not get reads `unknown`, never
    0; `lookup: unknown` means the whole lookup failed. Any other URL is
    refused — read it with `web_fetch`.
    """
    require_write()
    try:
        return curation.check_link(url)
    except LinkError as exc:
        raise ToolError(str(exc))
