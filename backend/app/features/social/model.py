"""The social feature's shapes: a Bluesky account as the posting agent reads it."""

from __future__ import annotations

from typing import TypedDict


class SocialError(ValueError):
    """A lookup, link or post the agent can correct, returned as a message."""


class Account(TypedDict):
    handle: str
    did: str
    name: str
    bio: str
    followers: int
    posts: int
