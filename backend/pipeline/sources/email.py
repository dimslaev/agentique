"""Newsletter (IMAP) pipeline source.

Reads recent emails from known newsletter senders in the "sub" mailbox and
turns each issue's links into items. Links are pulled out of the HTML by regex,
the obvious plumbing is dropped by rule, and each survivor is classified by one
Jev request: sponsor, plumbing, on-topic, and what kind of thing it points at.
What "resolving" an item means depends on that kind:

- a Product (a named launch) whose href is not the maker's own page — a
  write-up, a tweet mirror, an aggregator — has its canonical URL rediscovered
  by web search.
- an Article (a post someone wrote) IS its link. Searching for it would land
  on some other page about the same topic, so its href is followed instead,
  which resolves the redirect to the real destination. A product already
  linked first-party is resolved the same way.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from html import unescape
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from imap_tools import AND, MailBox

from app.platform.logging import log, short_error
from baml_client.sync_client import b
from baml_client.types import NewsletterItem, NewsletterItemKind, SearchCandidate
from pipeline import jev
from pipeline.fetching.http import BROWSER_HEADERS, fetch_with_timeout, tavily_search
from pipeline.types import RawItem
from pipeline.urls import hostname

IMAP_FOLDER = "sub"


@dataclass(frozen=True)
class ImapConfig:
    host: str
    port: int
    user: str
    password: str


def imap_config() -> ImapConfig:
    """Read lazily, so importing this module needs no IMAP environment."""
    host = os.environ.get("IMAP_HOST")
    user = os.environ.get("IMAP_USER")
    password = os.environ.get("IMAP_PASSWORD")
    if not host or not user or not password:
        raise RuntimeError("Missing IMAP env vars: IMAP_HOST, IMAP_USER, IMAP_PASSWORD")
    port = int(os.environ.get("IMAP_PORT", "993"))
    return ImapConfig(host=host, port=port, user=user, password=password)


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


# Beehiiv and TLDR pad the preheader with hundreds of these. Left in, they
# fill the whole leading context window of the first real links. U+034F is the
# "&#847;" that commonly pairs with them.
_ZERO_WIDTH_RE = re.compile("[\u200b-\u200f\ufeff\u00ad\u034f\u2060]")

# TLDR puts an item's description after its link, so the window leans forward.
CONTEXT_BEFORE = 300
CONTEXT_AFTER = 400
# Enough of the text after a link to name what it is — the product search
# query and SelectProductLink's description, not the stored content.
BLURB_CHARS = 200

_NON_HTTP_RE = re.compile(r"^(?!https?://)", re.IGNORECASE)
# Only the unambiguous cases. Anything subtler is Jev's is_admin question.
# Endpoints match only as the whole last path segment, so a post at
# /privacy-in-llms is not mistaken for /privacy.
_ADMIN_HREF_RE = re.compile(
    r"unsubscribe|manage[-_]?(?:preferences|subscription)|list-manage\.com"
    r"|view[-_]?in[-_]?browser|webversion"
    r"|/(?:preferences|subscribe|sign-?up|refer(?:ral)?|advertise|privacy(?:-policy)?"
    r"|terms(?:-of-(?:service|use))?)/?(?:$|[?#])",
    re.IGNORECASE,
)
_ADMIN_TEXT_RE = re.compile(
    r"^(?:unsubscribe|manage (?:your )?(?:preferences|subscription)"
    r"|update (?:your )?preferences|view (?:it |this email )?(?:in|on) (?:your )?"
    r"(?:browser|web)|view online|read online|subscribe|sign up|advertise(?: with us)?"
    r"|refer a friend|share|forward|privacy policy|terms(?: of service)?)[.!]?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Link:
    href: str
    anchor: str
    context: str
    blurb: str = field(default="", compare=False)


def _plain(fragment: str) -> str:
    text = unescape(_TAG_RE.sub(" ", fragment))
    # After unescape: the padding usually arrives as entities (&zwnj;, &#8203;).
    text = _ZERO_WIDTH_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()


def extract(html: str) -> list[Link]:
    """Every anchor in an email, with the plain text around it.

    The text is rendered once for the whole email and each anchor's offset
    into it recorded, so the context of one link can reach into the next.
    """
    html = _SCRIPT_RE.sub("", _STYLE_RE.sub("", html))
    pieces: list[str] = []
    length = 0
    spans: list[tuple[str, str, int, int]] = []

    def append(chunk: str) -> int:
        nonlocal length
        if not chunk:
            return length
        if pieces:
            pieces.append(" ")
            length += 1
        start = length
        pieces.append(chunk)
        length += len(chunk)
        return start

    pos = 0
    for m in _ANCHOR_RE.finditer(html):
        append(_plain(html[pos : m.start()]))
        anchor = _plain(m.group(2))
        start = append(anchor)
        spans.append((unescape(m.group(1)).strip(), anchor, start, start + len(anchor)))
        pos = m.end()
    append(_plain(html[pos:]))

    text = "".join(pieces)
    return [
        Link(
            href=href,
            anchor=anchor,
            context=text[max(0, start - CONTEXT_BEFORE) : end + CONTEXT_AFTER],
            blurb=text[end : end + BLURB_CHARS].strip(),
        )
        for href, anchor, start, end in spans
    ]


def _destination(href: str) -> str:
    return _unwrap_tracking_url(href) or href


def _known_host(href: str) -> str | None:
    """The destination's host, or None while an opaque tracker still hides it."""
    host = hostname(_destination(href))
    return None if not host or host in REDIRECTOR_HOSTS else host


# Many unrelated newsletters send from these. A post on writer.substack.com is
# someone else's content, not the sender's own site.
SHARED_SENDER_DOMAINS = (
    "substack.com",
    "beehiiv.com",
    "convertkit.com",
    "kit.com",
    "ghost.io",
    "buttondown.email",
    "mailchimp.com",
    "mcsv.net",
)


def _own_host(sender: str) -> str:
    """The sender's site, or "" when it sends through a shared platform."""
    host = sender.rpartition("@")[2].lower().removeprefix("www.")
    if any(_same_site(host, d) for d in SHARED_SENDER_DOMAINS):
        return ""
    return host


def _same_site(host: str, own_host: str) -> bool:
    return (
        host == own_host
        or host.endswith(f".{own_host}")
        or own_host.endswith(f".{host}")
    )


def _drop_reason(link: Link, own_host: str) -> str | None:
    if _NON_HTTP_RE.match(link.href):
        return "non_http"
    if not link.anchor:
        # An image tile. Its text twin, when there is one, carries the title.
        return "no_text"
    destination = _destination(link.href)
    if _ADMIN_HREF_RE.search(destination) or _ADMIN_TEXT_RE.match(link.anchor):
        return "admin"
    host = _known_host(link.href)
    if host is None:
        return None
    if _is_denied(destination):
        return "denied"
    if own_host and _same_site(host, own_host):
        return "own_host"
    return None


def prefilter(
    links: list[Link], own_host: str
) -> tuple[list[Link], dict[str, list[Link]]]:
    """Drop what is plumbing by rule, before any of it costs a request.

    Dedup runs last so an image tile dropped for having no text does not
    shadow the titled link to the same place.
    """
    own_host = own_host.lower().removeprefix("www.")
    kept: list[Link] = []
    dropped: dict[str, list[Link]] = {}
    seen: set[str] = set()
    for link in links:
        reason = _drop_reason(link, own_host)
        if reason is None:
            key = _canonical_url(_destination(link.href))
            if key in seen:
                reason = "duplicate"
            else:
                seen.add(key)
        if reason is None:
            kept.append(link)
        else:
            dropped.setdefault(reason, []).append(link)
    return kept, dropped


# The exact wording every threshold below was measured with (2026-09-22/23,
# TLDR and Pointer). Jev reads literally, so exclusions live in the question
# text, not in code after it. Rewording means re-measuring.
QUESTIONS = {
    "is_sponsor": jev.noul(
        "Is this link an advertisement or sponsored placement rather than editorial content?",
        "The surrounding text is an ad read, a sponsor blurb, a 'presented by' / 'brought to you by' segment, a free-trial or demo call-to-action, or a vendor pitch the newsletter was paid to run.",
        "The surrounding text is the newsletter's own editorial coverage of a news item.",
    ),
    "is_admin": jev.noul(
        "Is this link newsletter plumbing rather than a story?",
        "Unsubscribe, manage preferences, view in browser, read online, subscribe, archive, refer-a-friend, social profile, job board, podcast or merch link.",
        "A link to a specific external story, product or write-up.",
    ),
    # The exclusion list is load-bearing: without it a crypto post titled
    # "Bitcoin L2 agents: autonomous yield farming with onchain AI" scored
    # 0.85, with it 0.07.
    "is_ai_topic": jev.noul(
        "Is the linked item about artificial intelligence, machine learning, LLMs, or AI developer tooling?",
        "AI/ML models, agents, LLM infrastructure, AI research, AI products or AI developer tooling.",
        "Answer no for crypto, web3, blockchain or onchain topics even when they mention AI or agents. Also no for general programming with no AI angle, non-AI security, chip supply chain, funding rounds, hiring, politics, lawsuits and corporate drama.",
    ),
    "kind": jev.choice(
        "What is the newsletter pointing at with this link?",
        {
            "article": "A write-up someone authored: blog post, essay, paper, teardown, benchmark, guide, news story or analysis. The link itself is the thing to read.",
            "product": "A named product, model, tool, SDK or dataset a reader could go use. The link is an announcement or landing page for that launch.",
            "neither": "Anything else: an ad, newsletter plumbing, a social profile, a job posting or a section header.",
        },
    ),
    # Unmeasured, unlike the four above: a first draft. It only decides
    # whether a product costs a Tavily search, so a wrong answer costs a
    # search or loses the canonical page, never a sponsor let through.
    "is_first_party": jev.noul(
        "Is the destination host the canonical home of the thing this link describes?",
        "The host belongs to the maker: the vendor's own site, product page, model card, docs, or source repo.",
        "The host is a publication, aggregator, social mirror or content farm writing about it rather than the maker's own page.",
    ),
}

# Measured on the same two issues and nowhere else — there is no held-out set.
# Sponsor sits at 0.75, not 0.5: real sponsors landed 0.87-0.96 and the highest
# editorial link 0.64 (a promotional-sounding launch post). Do not tune past
# those issues without re-measuring.
ADMIN_THRESHOLD = 0.55
SPONSOR_THRESHOLD = 0.75
AI_TOPIC_THRESHOLD = 0.50
FIRST_PARTY_THRESHOLD = 0.50  # unmeasured

# Jev answered 152 links in 12.2s at this concurrency.
CLASSIFY_CONCURRENCY = 10


def verdict(answers: dict) -> str:
    """ "keep", or the reason a classified link is dropped."""
    if answers["is_admin"] > ADMIN_THRESHOLD:
        return "admin"
    if answers["is_sponsor"] > SPONSOR_THRESHOLD:
        return "sponsor"
    if answers["kind"] == "neither":
        return "neither"
    if answers["is_ai_topic"] < AI_TOPIC_THRESHOLD:
        return "off_topic"
    return "keep"


def _classify(link: Link) -> jev.Reply:
    host = _known_host(link.href)
    state = {
        "link_text": link.anchor,
        "destination_host": host or "unknown",
        "surrounding_newsletter_text": link.context,
    }
    return jev.ask(state, QUESTIONS)


def _item(link: Link, answers: dict, newsletter_name: str, email_date: str) -> dict:
    is_product = answers["kind"] == "product"
    return {
        "kind": NewsletterItemKind.Product
        if is_product
        else NewsletterItemKind.Article,
        "name": link.anchor,
        "description": link.blurb,
        "url": link.href,
        # Behind an opaque tracker Jev saw no host, so its answer is a guess.
        "first_party": _known_host(link.href) is not None
        and answers["is_first_party"] > FIRST_PARTY_THRESHOLD,
        "email_date": email_date,
        "newsletter_name": newsletter_name,
    }


def _extract_items(
    html: str, newsletter_name: str, email_date: str, own_host: str
) -> list[dict]:
    kept, dropped = prefilter(extract(html), own_host)
    reasons = {r: len(links) for r, links in dropped.items()}
    log(f"    {len(kept)} link(s) to classify, prefilter dropped {reasons}")

    items: list[dict] = []
    verdicts: dict[str, int] = {}
    cost = 0.0
    with ThreadPoolExecutor(max_workers=CLASSIFY_CONCURRENCY) as ex:
        futures = {ex.submit(_classify, link): link for link in kept}
        for f in as_completed(futures):
            link = futures[f]
            try:
                reply = f.result()
            except Exception as e:
                verdicts["failed"] = verdicts.get("failed", 0) + 1
                log(f'    Classify failed for "{link.anchor}": {short_error(e)}')
                continue
            cost += reply.cost
            v = verdict(reply.answers)
            verdicts[v] = verdicts.get(v, 0) + 1
            if v == "keep":
                items.append(_item(link, reply.answers, newsletter_name, email_date))

    log(f"    Jev verdicts {verdicts}, cost ${cost:.5f}")
    return items


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


def _resolve_article(item: dict) -> RawItem | None:
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
        # Left empty: the fetch step re-fetches anything this thin anyway.
        "content": "",
        "published_date": item["email_date"],
        "source": item["newsletter_name"],
    }


def _resolve_product(product: dict) -> RawItem | None:
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
        "content": "",
        "published_date": product["email_date"],
        "source": product["newsletter_name"],
    }


def _resolve_one(item: dict) -> RawItem | None:
    """Route an item to the resolution its kind needs. A product already linked
    at its maker's own page needs no search — its href is the answer."""
    if item["kind"] == NewsletterItemKind.Article or item["first_party"]:
        return _resolve_article(item)
    return _resolve_product(item)


def _resolve_items(raw: list[dict]) -> list[RawItem]:
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

    searched = sum(
        1
        for i in items
        if i["kind"] == NewsletterItemKind.Product and not i["first_party"]
    )
    log(
        f"  Resolving {len(items)} notable items "
        f"({searched} product(s) via search, {len(items) - searched} link(s) followed) "
        f"— {len(raw)} raw -> {len(unique)} unique -> {len(items)} notable"
    )

    articles: list[RawItem] = []
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
            items = _extract_items(html, name, email_date, _own_host(msg.from_ or ""))
            log(f"    Found {len(items)} items")
            raw.extend(items)

    return raw


def fetch_newsletter(
    sources: list[tuple[str, str]], lookback_days: int = LOOKBACK_DAYS
) -> list[RawItem]:
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
