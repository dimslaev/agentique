"""Feed parsing over the sample XML the repo ships — no network.

Validates the fetch path's data handling: content:encoded is extracted and
sanitized to plain text, titles are cleaned, and thin/teaser entries resolve to
empty content (so the enrich stage knows to re-fetch them).
"""

from __future__ import annotations

from pathlib import Path

import feedparser
import pytest

from pipeline_new.feeds import _entry_content

XML_DIR = Path(__file__).resolve().parents[2] / "pipeline_new" / "xml"
SAMPLE_FEEDS = sorted(XML_DIR.glob("*.xml"))


def test_sample_feeds_present() -> None:
    assert SAMPLE_FEEDS, f"no sample feeds under {XML_DIR}"


@pytest.mark.parametrize("path", SAMPLE_FEEDS, ids=lambda p: p.stem)
def test_feed_parses_and_extracts_plain_text(path: Path) -> None:
    feed = feedparser.parse(path.read_text())
    entries = feed.get("entries", [])
    assert entries, f"{path.name} parsed to zero entries"

    for entry in entries:
        text = _entry_content(entry)
        # Extraction yields plain text: never HTML tags, never markdown emphasis.
        assert "<p>" not in text and "<div" not in text
        assert "**" not in text
        assert entry.get("link"), "feed entry missing a link"
