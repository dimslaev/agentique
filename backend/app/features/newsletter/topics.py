"""The newsletter's email topics: the feed's topics, as Resend Topics.

Resend holds the subscription state (an email's unsubscribe link changes it
there directly), so this module only names the topics and maps each slug to
its Resend id. The Resend name is the feed's label; ids are matched by exact
name. Topics are created only through `python -m app.entry.cli.sync_topics`:
each is born with `default_subscription: opt_in`, which Resend never lets
change, so current subscribers keep getting every issue until they opt out
per topic.
"""

from __future__ import annotations

import resend

from app.core.settings import settings
from app.features.newsletter.model import IssueError

# slug -> label, the feed's 8 in its order
# (frontend/src/features/feed/model/topics.ts). The backend owns this list
# for email; the profile page reads it from the API.
TOPICS: dict[str, str] = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
    "open-weights": "Open weights",
    "small-models": "Small models",
    "generative-media": "Beyond text",
    "harness": "Harnesses",
    "make-it-fast": "Make it fast",
}

# Resend reads this once, at topic creation, and never lets it change: a new
# topic must default to subscribed, or current subscribers silently stop
# getting the issues they already get.
OPT_IN = "opt_in"


def _config() -> None:
    """Set the SDK's key, or refuse in `_sender`'s style. Topics are
    account-level, so the audience id is not needed here."""
    if not settings.RESEND_API_KEY:
        raise IssueError("Resend is not configured: RESEND_API_KEY unset.")
    resend.api_key = settings.RESEND_API_KEY


def topic_ids() -> dict[str, str]:
    """{slug: Resend topic id} for every topic that exists in Resend, matched
    by exact name. A topic not created yet is simply absent."""
    _config()
    by_name = {t["name"]: t["id"] for t in resend.Topics.list()["data"]}
    return {slug: by_name[label] for slug, label in TOPICS.items() if label in by_name}


def create_missing() -> list[tuple[str, str]]:
    """Create each topic of ours that Resend lacks, as (slug, id). Existing
    topics are left alone, so a second run creates nothing."""
    have = topic_ids()
    created: list[tuple[str, str]] = []
    for slug, label in TOPICS.items():
        if slug in have:
            continue
        made = resend.Topics.create({"name": label, "default_subscription": OPT_IN})
        created.append((slug, made["id"]))
    return created
