"""What the posting routine does on Bluesky: find a publisher's account, link and
follow it, and post an article with its author tagged."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlmodel import Session, select

from app.core.db.publisher import LinkPlatform, Publisher
from app.core.urls import hostname
from app.features.social import bluesky
from app.features.social.bluesky import Facet, Profile
from app.features.social.model import Account, SocialError

# Bluesky counts graphemes. len() counts code points, never fewer, so a text
# that passes here also passes there.
MAX_CHARS = 300
SEARCH_LIMIT = 5
# How far back a URL counts as already posted.
OWN_FEED_LIMIT = 100
MENTION = re.compile(r"(?<![\w@])@([a-z0-9-]+(?:\.[a-z0-9-]+)+)", re.I)
HASHTAG = re.compile(r"(?<!\S)#(\w+)")


def _account(p: Profile) -> Account:
    return {
        "handle": p["handle"],
        "did": p["did"],
        "name": p.get("displayName") or "",
        "bio": " ".join((p.get("description") or "").split()),
        "followers": p.get("followersCount") or 0,
        "posts": p.get("postsCount") or 0,
    }


def _publisher(session: Session, slug: str) -> Publisher:
    p = session.exec(select(Publisher).where(Publisher.slug == slug)).first()
    if p is None:
        raise SocialError(f"No publisher {slug}")
    return p


def find_account(session: Session, slug: str) -> list[Account]:
    """The publisher's linked account, or candidates to judge: a handle equal to
    its website host, then a search by its name."""
    p = _publisher(session, slug)
    linked = p.links.get(LinkPlatform.bluesky)
    if linked:
        return [_account(bluesky.profile(linked))]
    dids: list[str] = []
    website = p.links.get(LinkPlatform.website, "")
    site = hostname(website).removeprefix("www.")
    # A path (github.com/x, huggingface.co/x) means a shared host, whose handle
    # is the platform's account, not the publisher's.
    if site and not urlparse(website).path.strip("/"):
        try:
            dids.append(bluesky.resolve(site))
        except SocialError:
            pass
    # "Hugging Face Blog" finds nothing; "Hugging Face" finds hf.co.
    name = re.sub(r"\s+blog$", "", p.name, flags=re.I)
    dids += [a["did"] for a in bluesky.search(name, SEARCH_LIMIT)]
    if not dids:
        return []
    return [_account(pr) for pr in bluesky.profiles(list(dict.fromkeys(dids)))]


def link_account(session: Session, slug: str, handle: str) -> str:
    """Save `handle` as the publisher's account and follow it if we don't yet."""
    p = _publisher(session, slug)
    account = _account(bluesky.profile(handle))
    p.links = {**p.links, LinkPlatform.bluesky: account["handle"]}
    session.add(p)
    session.commit()
    token, me = bluesky.login()
    if bluesky.is_following(me, account["did"]):
        return f"Linked {slug} to @{account['handle']}, already followed"
    bluesky.create(
        token,
        me,
        "app.bsky.graph.follow",
        {
            "$type": "app.bsky.graph.follow",
            "subject": account["did"],
            "createdAt": datetime.now(UTC).isoformat(),
        },
    )
    return f"Linked {slug} to @{account['handle']}, followed"


def mention_facets(text: str) -> list[Facet]:
    """A mention facet per @handle, at UTF-8 byte offsets. Refuses an unknown handle."""
    facets: list[Facet] = []
    for m in MENTION.finditer(text):
        start = len(text[: m.start()].encode())
        end = start + len(m.group(0).encode())
        facets.append(
            {
                "index": {"byteStart": start, "byteEnd": end},
                "features": [
                    {
                        "$type": "app.bsky.richtext.facet#mention",
                        "did": bluesky.resolve(m.group(1)),
                    }
                ],
            }
        )
    return facets


def tag_facets(text: str) -> list[Facet]:
    """A hashtag facet per #tag, at UTF-8 byte offsets, so Bluesky links it."""
    facets: list[Facet] = []
    for m in HASHTAG.finditer(text):
        start = len(text[: m.start()].encode())
        end = start + len(m.group(0).encode())
        facets.append(
            {
                "index": {"byteStart": start, "byteEnd": end},
                "features": [
                    {"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}
                ],
            }
        )
    return facets


def post(text: str, url: str, title: str, description: str) -> str:
    """Post `text` with a link card for `url`. Refuses a URL we already posted."""
    if not text.strip():
        raise SocialError("Text is empty")
    if len(text) > MAX_CHARS:
        raise SocialError(f"Text is {len(text)} characters, the limit is {MAX_CHARS}")
    if not url.startswith("https://"):
        raise SocialError("url must be an https link")
    facets = mention_facets(text) + tag_facets(text)
    token, me = bluesky.login()
    if url in bluesky.card_urls(me, OWN_FEED_LIMIT):
        raise SocialError(f"Already posted {url}")
    uri = bluesky.create(
        token,
        me,
        "app.bsky.feed.post",
        {
            "$type": "app.bsky.feed.post",
            "text": text,
            "facets": facets,
            "langs": ["en"],
            "createdAt": datetime.now(UTC).isoformat(),
            "embed": {
                "$type": "app.bsky.embed.external",
                "external": {"uri": url, "title": title, "description": description},
            },
        },
    )
    rkey = uri.rsplit("/", 1)[1]
    return f"https://bsky.app/profile/{bluesky.own_handle()}/post/{rkey}"
