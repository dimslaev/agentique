"""Article title cleanup at ingest time."""

from __future__ import annotations

import re

HN_PREFIX_RE = re.compile(r"^(?:Show|Launch|Ask|Tell) HN:\s*", re.IGNORECASE)
# Newsletter labels: Console's "Beta: djs", TLDR's "Devin Apps (3 minute read)".
LABEL_PREFIX_RE = re.compile(r"^(?:Beta|Tool):\s+")
LABEL_SUFFIX_RE = re.compile(
    r"\s+\((?:Website|GitHub Repo|Sponsor|\d+ minute read)\)$", re.IGNORECASE
)


def clean_title(title: str) -> str:
    """Strip the HN prefix and newsletter labels a title may carry."""
    title = HN_PREFIX_RE.sub("", title)
    title = LABEL_PREFIX_RE.sub("", title)
    return LABEL_SUFFIX_RE.sub("", title).strip()
