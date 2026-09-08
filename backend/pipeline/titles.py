"""Article title cleanup at ingest time."""

from __future__ import annotations

import re

HN_PREFIX_RE = re.compile(r"^(?:Show|Launch|Ask|Tell) HN:\s*", re.IGNORECASE)


def clean_title(title: str) -> str:
    """Strip the ``Show HN:`` / ``Ask HN:`` style prefix a title may carry."""
    return HN_PREFIX_RE.sub("", title).strip()
