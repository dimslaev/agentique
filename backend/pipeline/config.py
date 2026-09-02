"""Every environment variable the pipeline reads, in one place.

Grouped by what each configures and read lazily — nothing here runs at import
time, so a piece that needs no IMAP, say, does not fail just because IMAP_* is
unset. This mirrors pipeline.db.get_engine() / pipeline.embedding.get_model():
lazy so importing pipeline modules in tests needs no environment at all.

Reads os.environ directly rather than app.core.config.settings, so the pipeline
stays decoupled from the backend's full Settings object.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote


def postgres_url() -> str:
    server = os.environ["POSTGRES_SERVER"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = quote(os.environ["POSTGRES_USER"], safe="")
    password = quote(os.environ.get("POSTGRES_PASSWORD", ""), safe="")
    db = os.environ.get("POSTGRES_DB", "")
    return f"postgresql+psycopg://{user}:{password}@{server}:{port}/{db}"


@dataclass(frozen=True)
class ImapConfig:
    host: str
    port: int
    user: str
    password: str


def imap_config() -> ImapConfig:
    host = os.environ.get("IMAP_HOST")
    user = os.environ.get("IMAP_USER")
    password = os.environ.get("IMAP_PASSWORD")
    if not host or not user or not password:
        raise RuntimeError("Missing IMAP env vars: IMAP_HOST, IMAP_USER, IMAP_PASSWORD")
    port = int(os.environ.get("IMAP_PORT", "993"))
    return ImapConfig(host=host, port=port, user=user, password=password)


def tavily_api_key() -> str:
    return os.environ["TAVILY_API_KEY"]


def residential_proxy_url() -> str | None:
    """A proxy for source fetches that get blocked direct (403/429/paywall).
    Metered, so callers only reach for it after a direct attempt fails."""
    return os.environ.get("RESIDENTIAL_PROXY_URL")


def keep_drop_threshold() -> float:
    """Auto-drop cutoff for the keep/drop pre-filter; 0 disables it. See
    pipeline.keep_drop for why the default is deliberately low (high recall)."""
    return float(os.environ.get("KEEP_DROP_PREFILTER_THRESHOLD", "0.15"))


def hn_min_points() -> int:
    """Upvotes an aged-out Hacker News story needs before it is worth an
    extraction and a scoring call. 0 disables the traction gate.

    A Show HN for a two-star repo finishes its life at 1-4 points; anything the
    community actually read clears 10 comfortably. See ``sources.hn`` for why
    this only applies once a story has had time to accumulate votes.
    """
    return int(os.environ.get("HN_MIN_POINTS", "10"))


def hn_min_comments() -> int:
    """Alternative to ``hn_min_points``: a story that got discussed is real even
    when the votes stayed flat. Either bar clears the gate."""
    return int(os.environ.get("HN_MIN_COMMENTS", "5"))


def hn_grace_hours() -> float:
    """How long a story is exempt from having any traction yet.

    Under this age a vote count says nothing - every story starts at 1 point.
    Rather than admit them blind (which is what filled the feed with noise) the
    source holds them back; the next run re-reads them with real numbers, still
    inside the 48h window. See ``sources.hn``.
    """
    return float(os.environ.get("HN_GRACE_HOURS", "6"))


def github_min_stars() -> int:
    """Stars a GitHub repo needs before we treat it as something builders use.
    0 disables the repo gate.

    Aimed at the "solo repo with two stars, posted by its author" case, not at
    ranking projects: a real tool that reaches an aggregator is well past this
    by the time it does. Repos under an owner on
    ``heuristics.KNOWN_REPO_OWNERS`` skip the check entirely.
    """
    return int(os.environ.get("GITHUB_MIN_STARS", "50"))


def github_token() -> str | None:
    """Optional PAT for the GitHub REST API. Unauthenticated is the default and
    is enough (60 requests/hour/IP, above what one run needs); a token raises
    that to 5000 if the pipeline ever polls harder."""
    return os.environ.get("GITHUB_TOKEN") or None


def dedup_dist_threshold() -> float:
    """Cosine-distance cutoff below which two articles are the same story;
    0 disables dedup entirely.

    Same-story pairs empirically sit at 0.29-0.35. The old shortlist used 0.45
    to favour recall because an LLM still made the final call — that call is
    gone, so this now drops on its own and sits at the bottom of the band
    instead. Erring tight costs a duplicate slipping through; erring loose
    silently deletes a real article, which is the worse failure.
    """
    return float(os.environ.get("DEDUP_DIST_THRESHOLD", "0.30"))


@dataclass(frozen=True)
class AlertConfig:
    resend_api_key: str | None
    from_email: str | None
    to_email: str | None
    project_name: str


def alert_config() -> AlertConfig:
    resend_api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("EMAILS_FROM_EMAIL")
    to_email = os.environ.get("PIPELINE_ALERT_EMAIL") or from_email
    project_name = os.environ.get("PROJECT_NAME") or "Agentique"
    return AlertConfig(
        resend_api_key=resend_api_key,
        from_email=from_email,
        to_email=to_email,
        project_name=project_name,
    )
