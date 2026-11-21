"""Source discovery's rules: who a probe can still lift, who comes back, who is
culled, and where a page's feed is."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.features.curation import sources
from app.features.curation.sources import (
    can_reach_rate,
    cull_reason,
    feed_links,
    reopened,
)

NOW = datetime(2026, 11, 21, tzinfo=UTC)


def test_a_firehose_is_beyond_any_probe() -> None:
    assert not can_reach_rate(20, 60)  # 30/90 at best, under 40%
    assert not can_reach_rate(8, 33)  # google-ai-blog
    assert can_reach_rate(3, 2)
    assert can_reach_rate(1, 0)


def test_only_an_approval_after_the_switch_reopens() -> None:
    off = NOW - timedelta(days=10)
    assert not reopened(None, NOW)  # switched off by hand
    assert not reopened(off, None)
    assert not reopened(off, off - timedelta(days=1))
    assert reopened(off, off + timedelta(days=1))


def test_cull_on_zero_approvals_or_silence() -> None:
    recent = NOW - timedelta(days=5)
    assert cull_reason(0, 14, recent, NOW) == "culled 0/14 90d 2026-11-21"
    assert cull_reason(0, 9, recent, NOW) is None
    assert cull_reason(1, 30, recent, NOW) is None
    old = NOW - timedelta(days=121)
    assert cull_reason(5, 1, old, NOW) == (
        f"culled silent since {old.date()} 2026-11-21"
    )


def test_declared_feeds_come_before_the_common_paths() -> None:
    html = (
        '<link rel="stylesheet" href="/s.css">'
        '<link rel="alternate" type="application/rss+xml" href="/blog/rss">'
        '<link rel="Alternate" type="application/atom+xml" href="https://x.dev/feed">'
    )
    links = feed_links(html, "https://x.dev/")
    assert links[:3] == [
        "https://x.dev/blog/rss",
        "https://x.dev/feed",
        "https://x.dev/rss.xml",
    ]
    assert len(links) == len(set(links))


def test_only_a_blocked_fetch_goes_through_the_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str | None] = []

    def fetch(url: str, proxy: str | None = None, **_: object) -> httpx.Response:
        calls.append(proxy)
        return httpx.Response(404 if url.endswith("/missing") else 403)

    monkeypatch.setattr(sources, "RESIDENTIAL_PROXY_URL", "http://proxy")
    monkeypatch.setattr(sources, "fetch_with_timeout", fetch)
    assert sources._get("https://x.dev/missing") == b""
    assert calls == [None]
    calls.clear()
    assert sources._get("https://x.dev/blocked") == b""
    assert calls == [None, "http://proxy"]
