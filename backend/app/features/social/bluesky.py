"""Bluesky over XRPC: public reads, and writes as agentique's own account.

Reads go to the public AppView and need no login. Writes log in with an app
password, one session per call: the routine makes a handful a day.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TypedDict

import httpx

from app.features.social.model import SocialError

PUBLIC = "https://public.api.bsky.app/xrpc"
PDS = "https://bsky.social/xrpc"
TIMEOUT = 20.0


class Profile(TypedDict, total=False):
    handle: str
    did: str
    displayName: str
    description: str
    followersCount: int
    postsCount: int


class ByteSlice(TypedDict):
    byteStart: int
    byteEnd: int


# A mention carries `did`, a hashtag `tag`.
Feature = TypedDict("Feature", {"$type": str, "did": str, "tag": str}, total=False)


class Facet(TypedDict):
    index: ByteSlice
    features: list[Feature]


def own_handle() -> str:
    return os.environ.get("BLUESKY_HANDLE", "agentique.ch")


def _checked(resp: httpx.Response) -> httpx.Response:
    if resp.status_code == 400:
        # Bluesky's way of saying the handle or record does not exist.
        raise SocialError(resp.json().get("message", resp.text))
    resp.raise_for_status()
    return resp


def _get(method: str, **params: str | int | list[str]) -> httpx.Response:
    return _checked(httpx.get(f"{PUBLIC}/{method}", params=params, timeout=TIMEOUT))


def resolve(handle: str) -> str:
    did: str = _get("com.atproto.identity.resolveHandle", handle=handle).json()["did"]
    return did


def profile(actor: str) -> Profile:
    p: Profile = _get("app.bsky.actor.getProfile", actor=actor).json()
    return p


def profiles(actors: list[str]) -> list[Profile]:
    ps: list[Profile] = _get("app.bsky.actor.getProfiles", actors=actors).json()[
        "profiles"
    ]
    return ps


def search(query: str, limit: int) -> list[Profile]:
    found: list[Profile] = _get(
        "app.bsky.actor.searchActors", q=query, limit=limit
    ).json()["actors"]
    return found


def card_urls(actor: str, limit: int) -> set[str]:
    """The link-card URLs of the actor's latest posts."""
    feed = _get("app.bsky.feed.getAuthorFeed", actor=actor, limit=limit).json()
    return {
        e["post"].get("embed", {}).get("external", {}).get("uri", "")
        for e in feed.get("feed", [])
    }


def login() -> tuple[str, str]:
    """An access token and the account's DID."""
    password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not password:
        raise SocialError("BLUESKY_APP_PASSWORD is not set on the server")
    session = _checked(
        httpx.post(
            f"{PDS}/com.atproto.server.createSession",
            json={"identifier": own_handle(), "password": password},
            timeout=TIMEOUT,
        )
    ).json()
    return session["accessJwt"], session["did"]


def create(token: str, did: str, collection: str, record: Mapping[str, object]) -> str:
    """Write one record to the account's repo and return its at:// URI."""
    uri: str = _checked(
        httpx.post(
            f"{PDS}/com.atproto.repo.createRecord",
            json={"repo": did, "collection": collection, "record": record},
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
    ).json()["uri"]
    return uri
