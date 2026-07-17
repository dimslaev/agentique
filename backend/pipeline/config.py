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


def postgres_url() -> str:
    server = os.environ["POSTGRES_SERVER"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ["POSTGRES_USER"]
    password = os.environ.get("POSTGRES_PASSWORD", "")
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
