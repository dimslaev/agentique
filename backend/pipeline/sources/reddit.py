"""Reddit source — the model-release subreddits, via the public listing JSON.

r/LocalLLaMA and r/MachineLearning surface weight drops, quantizations and
paper threads hours before a blog or an aggregator picks them up, and often
for releases that never get written up anywhere else. Both are already
on-topic by construction, so unlike Hacker News this source needs no keyword
gate — the subreddit *is* the gate.

No API key: ``/r/<sub>/top.json`` is the same listing the website renders, and
it is read anonymously. It does need a browser User-Agent (Reddit serves a 403
to the default client UA), which ``BROWSER_HEADERS`` already carries.

What comes back is a mix of link posts (the interesting case — they point at a
model card, a repo or a blog) and self posts (a discussion thread, whose body
is the content). Link posts arrive with no content and are filled by
``extract_content`` here, then anything still thin is caught again by the fetch
step's ``_with_content``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from app.platform.logging import log
from pipeline.freshness import is_within_window
from pipeline.sources.extract_content import extract_content
from pipeline.sources.http import BROWSER_HEADERS, fetch_with_timeout
from pipeline.titles import clean_title
from pipeline.types import FetchedArticle
from pipeline.urls import hostname

SUBREDDITS = ("LocalLLaMA", "MachineLearning")
LISTING_URL = "https://www.reddit.com/r/{sub}/top.json?t=day&limit={limit}"
LISTING_LIMIT = 50

# Upvotes a post needs before it is worth an extraction and a scoring call. Both
# subreddits push a real release well past this within the day; below it is
# mostly help threads and single-comment questions.
MIN_SCORE = 25

# Hosts whose posts are an image, a clip or a paywalled aggregator — nothing
# trafilatura can turn into an article. Dropped here rather than fetched and
# discarded downstream.
_MEDIA_HOSTS = frozenset(
    {
        "i.redd.it",
        "v.redd.it",
        "i.imgur.com",
        "imgur.com",
        "youtube.com",
        "youtu.be",
        "redd.it",
    }
)


def _to_article(post: dict) -> FetchedArticle | None:
    """One listing entry's ``data`` object -> a fetched article, or None.

    Gates, cheapest first: it must be a live, non-stickied, SFW post over
    ``MIN_SCORE``, it must fall inside the recency window, and it must point
    somewhere with text to extract. A self post keeps its permalink as the URL
    and its ``selftext`` as content; a link post takes the linked URL and
    leaves content empty for ``extract_content`` to fill.
    """
    title = (post.get("title") or "").strip()
    if not title:
        return None
    if post.get("stickied") or post.get("over_18") or post.get("removed_by_category"):
        return None
    if (post.get("score") or 0) < MIN_SCORE:
        return None

    created = post.get("created_utc")
    published = (
        datetime.fromtimestamp(created, tz=UTC).isoformat()
        if isinstance(created, int | float)
        else None
    )
    if not is_within_window(published):
        return None

    permalink = f"https://www.reddit.com{post.get('permalink') or ''}"
    if post.get("is_self"):
        url, content = permalink, (post.get("selftext") or "").strip()
    else:
        url, content = (post.get("url") or "").strip(), ""
        if not url or hostname(url) in _MEDIA_HOSTS:
            return None

    return {
        "title": clean_title(title),
        "url": url,
        "content": content,
        "published_date": published or datetime.now(UTC).isoformat(),
        "source": "Reddit",
    }


def _fetch_subreddit(sub: str) -> list[FetchedArticle]:
    url = LISTING_URL.format(sub=sub, limit=LISTING_LIMIT)
    try:
        resp = fetch_with_timeout(url, headers=BROWSER_HEADERS)
        resp.raise_for_status()
        children = resp.json()["data"]["children"]
    except Exception as e:
        log(f"  r/{sub} fetch failed: {e}")
        return []

    articles = [a for c in children if (a := _to_article(c.get("data") or {}))]
    log(f"  r/{sub}: {len(articles)} of {len(children)} posts kept")
    return articles


def fetch_reddit() -> list[FetchedArticle]:
    log(f"Fetching Reddit ({', '.join('r/' + s for s in SUBREDDITS)})...")

    with ThreadPoolExecutor(max_workers=len(SUBREDDITS)) as executor:
        results = list(executor.map(_fetch_subreddit, SUBREDDITS))

    # The two subreddits cross-post the same release often enough to matter, and
    # a URL seen twice would be two scoring calls for one story.
    seen: set[str] = set()
    articles: list[FetchedArticle] = []
    for a in (a for batch in results for a in batch):
        if a["url"] in seen:
            continue
        seen.add(a["url"])
        articles.append(a)

    log(f"Reddit: {len(articles)} posts")
    return extract_content(articles)
