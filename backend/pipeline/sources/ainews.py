"""AI News source - extracts sub-stories from the news.smol.ai RSS feed."""

from __future__ import annotations

import re
from html import unescape

from app.platform.logging import log
from pipeline.freshness import is_within_window
from pipeline.sources.http import fetch_with_timeout
from pipeline.types import FetchedArticle
from pipeline.urls import hostname

FEED_URL = "https://news.smol.ai/rss.xml"
MAX_CONTENT_LENGTH = 1400
MIN_REDDIT_BODY_LENGTH = 120
MIN_TWITTER_TITLE_LENGTH = 10


# --- minimal RSS parsing (no feedparser dep for this source) ---


def _pick_tag(block: str, tag: str) -> str:
    match = re.search(rf"<{tag}>([\s\S]*?)</{tag}>", block)
    if not match:
        return ""
    val = match.group(1)
    cdata = re.match(r"^<!\[CDATA\[([\s\S]*)\]\]>$", val)
    return cdata.group(1) if cdata else val


def _parse_feed(xml: str) -> list[dict]:
    items = []
    for chunk in xml.split("<item>")[1:]:
        body = chunk.split("</item>")[0]
        items.append(
            {
                "title": _pick_tag(body, "title"),
                "link": _pick_tag(body, "link"),
                "content_html": unescape(_pick_tag(body, "content:encoded")),
                "pub_date": _pick_tag(body, "pubDate"),
            }
        )
    return items


# --- HTML helpers ---


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _first_bold(html: str) -> str:
    m = re.search(r"<strong[^>]*>([\s\S]*?)</strong>", html)
    return _strip_tags(m.group(1)) if m else ""


def _collect_links(html: str) -> list[dict]:
    return [
        {
            "url": m.group(1),
            "host": hostname(m.group(1)),
            "text": _strip_tags(m.group(2)),
        }
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', html)
    ]


def _slice_section(html: str, heading_rx: re.Pattern) -> str:
    start = heading_rx.search(html)
    if not start:
        return ""
    after = html[start.end() :]
    next_h1 = re.search(r"<h1[^>]*>", after, re.IGNORECASE)
    return after[: next_h1.start()] if next_h1 else after


BLOG_HOST_RX = re.compile(
    r"\b(openai|anthropic|deepmind|google|meta|microsoft|nvidia|mistral|unsloth|"
    r"databricks|cohere|stability|perplexity|vercel|modal|together|replicate|groq)\b"
)

PRIMARY_PRIORITY = ["github", "huggingface", "arxiv", "blog", "reddit", "tweet"]

_JUNK_HOSTS = {
    "news.smol.ai",
    "latent.space",
    "support.substack.com",
    "i.redd.it",
    "preview.redd.it",
}


def _classify_host(host: str) -> str | None:
    if host in ("github.com",) or host.endswith(".github.io"):
        return "github"
    if host in ("huggingface.co", "hf.co"):
        return "huggingface"
    if host in ("arxiv.org", "ar5iv.labs.arxiv.org"):
        return "arxiv"
    if (
        BLOG_HOST_RX.search(host)
        or host.endswith(".ai")
        or host.endswith(".dev")
        or "substack.com" in host
    ):
        return "blog"
    if host in ("reddit.com",) or host.endswith(".reddit.com"):
        return "reddit"
    if host in ("x.com", "twitter.com"):
        return "tweet"
    return None


def _is_junk(link: dict) -> bool:
    if not link["url"]:
        return True
    if link["host"] in _JUNK_HOSTS:
        return True
    if "twitter.com/i/lists/" in link["url"] or "x.com/i/" in link["url"]:
        return True
    return False


def _pick_primary(links: list[dict]) -> dict:
    clean = [lnk for lnk in links if not _is_junk(lnk)]
    if not clean:
        return {"url": "", "kind": "other"}
    for kind in PRIMARY_PRIORITY:
        hit = next((lnk for lnk in clean if _classify_host(lnk["host"]) == kind), None)
        if hit:
            return {"url": hit["url"], "kind": kind}
    return {"url": clean[0]["url"], "kind": "other"}


# --- Twitter Recap ---


def _extract_twitter_recap(html: str) -> dict | None:
    region = _slice_section(
        html, re.compile(r"<h1[^>]*>\s*AI Twitter Recap\s*</h1>", re.IGNORECASE)
    )
    if not region:
        return None
    title = _first_bold(region)
    if not title or len(title) < MIN_TWITTER_TITLE_LENGTH:
        return None
    primary = _pick_primary(_collect_links(region))
    if not primary["url"]:
        return None
    bullets = [
        _strip_tags(m.group(1)) for m in re.finditer(r"<li>([\s\S]*?)</li>", region)
    ][:3]
    content = " ".join(bullets) or _strip_tags(region)
    return {
        "title": title,
        "url": primary["url"],
        "content": content[:MAX_CONTENT_LENGTH],
    }


# --- Reddit Recap ---

REDDIT_ANCHOR_RX = re.compile(
    r'<a[^>]+href="(https?://(?:www\.)?reddit\.com/r/[^"]+/comments/[^"]+)"[^>]*>([\s\S]*?)</a>'
)


def _extract_reddit_recap(html: str) -> list[dict]:
    region = _slice_section(
        html, re.compile(r"<h1[^>]*>\s*AI Reddit Recap\s*</h1>", re.IGNORECASE)
    )
    if not region:
        return []

    anchors = [
        {
            "url": m.group(1),
            "title": _strip_tags(m.group(2)),
            "start": m.start(),
            "end": m.end(),
        }
        for m in REDDIT_ANCHOR_RX.finditer(region)
    ]

    stories = []
    for i, anchor in enumerate(anchors):
        next_start = anchors[i + 1]["start"] if i + 1 < len(anchors) else len(region)
        after = region[anchor["end"] :]
        heading_rel = re.search(r"<h[123][^>]*>", after, re.IGNORECASE)
        heading_abs = (
            anchor["end"] + heading_rel.start() if heading_rel else len(region)
        )
        body_end = min(next_start, heading_abs)
        body = region[anchor["start"] : body_end]
        content = _strip_tags(body)
        if len(content) < MIN_REDDIT_BODY_LENGTH:
            continue
        primary = _pick_primary(_collect_links(body))
        stories.append(
            {
                "title": anchor["title"] or "(untitled)",
                "url": primary["url"] or anchor["url"],
                "content": content[:MAX_CONTENT_LENGTH],
            }
        )
    return stories


# --- fetch ---


def fetch_ai_news() -> list[FetchedArticle]:
    log("Fetching AI News feed...")
    try:
        resp = fetch_with_timeout(FEED_URL)
        if not resp.is_success:
            raise ValueError(f"Status {resp.status_code}")
        xml = resp.text
    except Exception as e:
        log(f"  AI News fetch FAILED: {e}")
        return []

    items = [it for it in _parse_feed(xml) if is_within_window(it["pub_date"])]
    log(f"  AI News: {len(items)} issues within window")

    articles: list[FetchedArticle] = []
    for item in items:
        if re.match(r"^not much happened", item["title"], re.IGNORECASE):
            continue
        twitter = _extract_twitter_recap(item["content_html"])
        if twitter:
            articles.append(
                {
                    **twitter,
                    "published_date": item["pub_date"],
                    "source": "AI News",
                }
            )
        for reddit in _extract_reddit_recap(item["content_html"]):
            articles.append(
                {
                    **reddit,
                    "published_date": item["pub_date"],
                    "source": "AI News",
                }
            )

    by_url: dict[str, FetchedArticle] = {}
    for a in articles:
        if a["url"] not in by_url:
            by_url[a["url"]] = a

    log(f"AI News: {len(by_url)} articles extracted")
    return list(by_url.values())
