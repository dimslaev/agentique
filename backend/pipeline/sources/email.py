"""Newsletter (IMAP) pipeline source.

Reads recent emails from known newsletter senders in the "sub" mailbox and
extracts the items each issue reports on via BAML. What "resolving" means
depends on the kind:

- a Product (a named launch) has no trustworthy href in the mail — newsletter
  links are tracking redirects — so its identity comes from the text and its
  canonical URL is rediscovered by web search.
- an Article (a post someone wrote) IS its link. Searching for it would land
  on some other page about the same topic, so its href is followed instead,
  which resolves the redirect to the real destination.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from html import unescape
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from imap_tools import AND, MailBox

from app.platform.logging import log, short_error
from baml_client.sync_client import b
from baml_client.types import NewsletterItem, NewsletterItemKind, SearchCandidate
from pipeline.config import ImapConfig, imap_config
from pipeline.sources.http import BROWSER_HEADERS, fetch_with_timeout, tavily_search
from pipeline.types import FetchedArticle
from pipeline.urls import hostname

IMAP_FOLDER = "sub"

# The product path spends one LLM call per item, and the LLM provider caps
# concurrent requests well below its per-minute quota: bursts past a handful of
# parallel calls come back 429 while the quota sits nearly untouched. Kept low
# for that reason, not for politeness — the retry policy on the BAML client
# absorbs the rest.
RESOLVE_CONCURRENCY = 3

# How far back to look. Selecting by date rather than by the unread flag keeps
# the mailbox read-only and makes a run reproducible — the same window returns
# the same issues however the mail was read. The pipeline runs daily, so this
# will drop to 1 once the channel is trusted; 7 is a deliberate overlap while
# it is being watched. Anything an earlier run already ingested is dropped
# downstream by the URL/dedup steps, not here.
LOOKBACK_DAYS = 7

# Never a product's first-party source: social posts, video, aggregators/content farms.
DENY_DOMAINS = [
    "x.com",
    "twitter.com",
    "t.co",
    "linkedin.com",
    "reddit.com",
    "threads.net",
    "mastodon.social",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "digg.com",
    "medium.com",
    "news.ycombinator.com",
]

# Campaign junk that survives a redirect. Stripped so the same post linked from
# two issues is one URL by the time dedup sees it.
TRACKING_PARAMS = (
    "utm_",
    "_bhlid",
    "aid",  # beehiiv's per-subscriber id
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref_src",
)

# Hosts that only ever redirect. Resolving to one of these means the redirect
# did not actually resolve — the tracker answered with a JS bounce page instead
# of a Location header — so the item is dropped rather than stored pointing at
# a link that dies with the campaign.
REDIRECTOR_HOSTS = (
    "tracking.tldrnewsletter.com",
    "links.tldrnewsletter.com",
    "link.mail.beehiiv.com",
    "email.mg.substack.com",
)

# TLDR-style trackers carry the destination inside their own path, either
# percent-encoded ("/CL0/https:%2F%2Fexample.com%2Fpost") or literal, followed
# by their message id and click token. Unwrapping it beats a network round trip
# to learn a URL the mail already states.
_EMBEDDED_URL_RE = re.compile(r"https?(?::|%3A)(?:/|%2F){2}.+", re.IGNORECASE)
_TRACKER_TAIL_RE = re.compile(r"/\d+/[0-9a-f]{8,}.*$", re.IGNORECASE)

_STYLE_RE = re.compile(r"<style[^>]*>[\s\S]*?</style>", re.IGNORECASE)
_SCRIPT_RE = re.compile(r"<script[^>]*>[\s\S]*?</script>", re.IGNORECASE)
_ANCHOR_RE = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)</a>', re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _match_sender(address: str, sources: list[tuple[str, str]]) -> str | None:
    addr = address.lower()
    for pattern, name in sources:
        p = pattern.lower()
        if addr.endswith(p) if p.startswith("@") else addr == p:
            return name
    return None


def _html_to_text(html: str) -> str:
    """Strip an email's HTML to text, keeping anchor text with hrefs as a weak
    hint. Hrefs are usually tracking redirects, so product identity comes from
    the surrounding words, not the link.
    """
    cleaned = _STYLE_RE.sub("", html)
    cleaned = _SCRIPT_RE.sub("", cleaned)

    def _anchor(m: re.Match[str]) -> str:
        text = _TAG_RE.sub("", m.group(2)).strip()
        return f"[{text}]({m.group(1)})" if text else ""

    cleaned = _ANCHOR_RE.sub(_anchor, cleaned)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned[:50_000]


def _extract_items(html: str, newsletter_name: str, email_date: str) -> list[dict]:
    text = _html_to_text(html)
    if not text:
        return []
    try:
        items = b.ExtractItems(text)
    except Exception as e:
        log(f"  Failed to extract items from {newsletter_name}: {e}")
        return []
    return [
        {
            "kind": item.kind,
            "name": item.name.strip(),
            "description": (item.description or "").strip(),
            # Only an Article carries one, and it is still the raw redirect here.
            "url": (item.url or "").strip(),
            "email_date": email_date,
            "newsletter_name": newsletter_name,
        }
        for item in items
        if item.name and item.name.strip()
    ]


def _is_denied(url: str) -> bool:
    host = hostname(url)
    if not host:
        return True
    return any(host == d or host.endswith(f".{d}") for d in DENY_DOMAINS)


def _drop_tracking_params(query: str) -> str:
    kept = [
        (k, v)
        for k, v in parse_qsl(query, keep_blank_values=True)
        if not any(k.lower().startswith(t) for t in TRACKING_PARAMS)
    ]
    return urlencode(kept)


def _canonical_url(url: str) -> str:
    """One URL per destination: campaign params dropped, trailing slash gone.

    Params are removed by name rather than whitelisted — a whitelist would
    break every link that needs an id or a page number. The fragment gets the
    same treatment because newsletters append their params after it
    ("#section?utm_source=..."), and the trailing slash goes because the same
    post arrives with and without one and would otherwise dedup as two.
    """
    parts = urlsplit(url)
    fragment = parts.fragment
    if "?" in fragment:
        anchor, _, frag_query = fragment.partition("?")
        stripped = _drop_tracking_params(frag_query)
        fragment = f"{anchor}?{stripped}" if stripped else anchor
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        parts._replace(
            netloc=parts.netloc.lower(),
            path=path,
            query=_drop_tracking_params(parts.query),
            fragment=fragment,
        )
    )


def _unwrap_tracking_url(url: str) -> str | None:
    """The destination a tracker embedded in its own path, or None if it hides
    it behind an opaque token."""
    match = _EMBEDDED_URL_RE.search(urlsplit(url).path)
    if not match:
        return None
    inner = _TRACKER_TAIL_RE.sub("", unquote(match.group(0)))
    return inner if hostname(inner) else None


def _resolve_article(item: dict) -> FetchedArticle | None:
    """One article -> its real URL, recovered from the newsletter's redirect.

    Unwrap first, follow only if that fails: most trackers spell the
    destination out in their path, and a request that teaches us nothing the
    mail already said is a request worth not making — the fetch step will hit
    the real page for its content anyway. Opaque tokens leave no choice, and
    for those it is a GET rather than a HEAD: these redirectors routinely
    answer a HEAD with a 405 or with no Location at all. httpx follows the
    chain, so the response's own url is the destination.
    """
    name = item["name"]
    url = item["url"]
    if not url:
        log(f'    Dropped "{name}": article with no link')
        return None

    final = _unwrap_tracking_url(url)
    if final is None:
        try:
            resp = fetch_with_timeout(url, headers=BROWSER_HEADERS)
        except Exception as e:
            log(f'    Redirect resolution failed for "{name}": {short_error(e)}')
            return None
        final = str(resp.url)
        if resp.status_code >= 400:
            # The redirect still resolved, so the destination is known and
            # worth keeping — the content re-fetch in the fetch step decides
            # whether it is reachable, and drops it if not.
            log(f'    "{name}": {resp.status_code} from {hostname(final)}, kept')

    final = _canonical_url(final)
    if hostname(final) in REDIRECTOR_HOSTS:
        log(f'    Dropped "{name}": still a redirect ({hostname(final)})')
        return None
    if _is_denied(final):
        log(f'    Dropped "{name}": resolved to a denied domain ({hostname(final)})')
        return None

    return {
        "title": name,
        "url": final,
        "content": item["description"],
        "published_date": item["email_date"],
        "source": item["newsletter_name"],
    }


def _resolve_product(product: dict) -> FetchedArticle | None:
    """One product -> one canonical URL, or None if nothing is a clean first-party source."""
    name = product["name"]
    description = product["description"]
    query = f"{name} {description}".strip()

    try:
        results = tavily_search(query)
    except Exception as e:
        log(f'    Search failed for "{name}": {e}')
        return None

    results = [r for r in results if not _is_denied(r["url"])]
    if not results:
        log(f'    No usable search result for "{name}"')
        return None

    try:
        choice = b.SelectProductLink(
            name,
            description,
            [
                SearchCandidate(
                    title=r["title"], url=r["url"], snippet=r["description"]
                )
                for r in results
            ],
        )
    except Exception as e:
        log(f'    Link selection failed for "{name}": {e}')
        return None

    # index is 1-based; 0 means "no candidate is a clean first-party source".
    picked = results[choice.index - 1] if choice.index >= 1 else None
    if not picked:
        log(f'    Dropped "{name}": no first-party result among candidates')
        return None

    return {
        "title": name,
        "url": _canonical_url(picked["url"]),
        "content": description,
        "published_date": product["email_date"],
        "source": product["newsletter_name"],
    }


def _resolve_one(item: dict) -> FetchedArticle | None:
    """Route an item to the resolution its kind needs."""
    if item["kind"] == NewsletterItemKind.Article:
        return _resolve_article(item)
    return _resolve_product(item)


def _resolve_items(raw: list[dict]) -> list[FetchedArticle]:
    """Dedupe items by name across all issues in this run, drop the un-notable
    ones, then resolve each survivor to a URL.

    Deduping by name and not by URL is deliberate: a product has no URL yet at
    this point, and the same launch is written up by two newsletters under the
    same name. Articles that survive as distinct names but resolve to one URL
    are collapsed after resolution.
    """
    if not raw:
        return []

    by_name: dict[str, dict] = {}
    for item in raw:
        by_name.setdefault(item["name"].lower(), item)
    unique = list(by_name.values())

    items = unique
    try:
        keep = b.SelectNotableItems(
            [
                NewsletterItem(
                    kind=i["kind"],
                    name=i["name"],
                    description=i["description"],
                    url=i["url"] or None,
                )
                for i in unique
            ]
        )
        keep_idx = set(keep)
        selected = [i for n, i in enumerate(unique) if (n + 1) in keep_idx]
        if selected:  # guard against a degenerate empty response dropping everything
            items = selected
    except Exception as e:
        log(f"  Notability filter failed, resolving all: {e}")

    products = sum(1 for i in items if i["kind"] == NewsletterItemKind.Product)
    log(
        f"  Resolving {len(items)} notable items "
        f"({products} product(s) via search, {len(items) - products} article link(s)) "
        f"— {len(raw)} raw -> {len(unique)} unique -> {len(items)} notable"
    )

    articles: list[FetchedArticle] = []
    seen_urls: set[str] = set()
    with ThreadPoolExecutor(max_workers=RESOLVE_CONCURRENCY) as ex:
        futures = [ex.submit(_resolve_one, i) for i in items]
        for f in as_completed(futures):
            article = f.result()
            if article and article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                articles.append(article)

    log(f"  Resolved {len(articles)}/{len(items)} items to URLs")
    return articles


def _run_imap_fetch(
    config: ImapConfig, sources: list[tuple[str, str]], lookback_days: int
) -> list[dict]:
    """One connect -> fetch -> logout cycle. Two passes: headers only to find
    matches in the window (avoids downloading full bodies of unrelated mail),
    then full source for matched UIDs only.

    Nothing is flagged: the window is the selection, so leaving read state
    alone keeps the mailbox usable by a human and a failed run repeatable.
    """
    raw: list[dict] = []
    since = date.today() - timedelta(days=lookback_days)

    with MailBox(config.host, port=config.port).login(
        config.user, config.password, initial_folder=IMAP_FOLDER
    ) as mb:
        matches: dict[str, str] = {}
        for msg in mb.fetch(AND(date_gte=since), mark_seen=False, headers_only=True):
            name = _match_sender(msg.from_ or "", sources)
            if name:
                matches[msg.uid] = name

        log(f"  Found {len(matches)} newsletter emails since {since.isoformat()}")
        if not matches:
            return raw

        for msg in mb.fetch(
            AND(uid=",".join(matches.keys())), mark_seen=False, headers_only=False
        ):
            name = matches.get(msg.uid)
            if not name:
                continue

            subject = msg.subject or "(no subject)"
            log(f"  Processing: {name} ({subject})")

            html = msg.html or msg.text or ""
            if not html:
                log("    No HTML content, skipping")
                continue

            email_date = (msg.date or datetime.now(UTC)).isoformat()
            items = _extract_items(html, name, email_date)
            log(f"    Found {len(items)} items")
            raw.extend(items)

    return raw


def fetch_newsletter(
    sources: list[tuple[str, str]], lookback_days: int = LOOKBACK_DAYS
) -> list[FetchedArticle]:
    if not sources:
        log("Newsletter: no sources configured, skipping")
        return []

    config = imap_config()
    log(f"Connecting to {config.host} as {config.user}...")

    try:
        raw = _run_imap_fetch(config, sources, lookback_days)
    except Exception as e:
        log(f"Newsletter fetch failed: {e}")
        return []

    articles = _resolve_items(raw)
    log(f"Newsletter: {len(articles)} articles extracted")
    return articles
