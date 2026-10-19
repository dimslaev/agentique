"""The sign-in and welcome mails: built from the templates beside this module,
sent through `app.core.email`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.email import render_email_template, send_email
from app.core.settings import settings

logger = logging.getLogger(__name__)

TEMPLATES = Path(__file__).parent


@dataclass
class EmailData:
    html_content: str
    subject: str


def sign_in_link(login_token: str) -> str:
    return f"{settings.FRONTEND_HOST}/auth?token={login_token}"


def generate_welcome_email(login_token: str) -> EmailData:
    html_content = render_email_template(
        template=TEMPLATES / "welcome.html",
        context={"link": sign_in_link(login_token)},
    )
    return EmailData(html_content=html_content, subject="Welcome to Agentique")


def generate_sign_in_email(login_token: str) -> EmailData:
    html_content = render_email_template(
        template=TEMPLATES / "sign_in.html",
        context={"link": sign_in_link(login_token)},
    )
    return EmailData(html_content=html_content, subject="Sign in to Agentique")


def send_link_email(email_to: str, email_data: EmailData, login_token: str) -> None:
    """Runs after the response: a failed send must not fail the request, and the
    caller's answer must not depend on whether the account exists."""
    if settings.ENVIRONMENT == "development":
        logger.info(
            "[dev] Sign-in link for %s: %s", email_to, sign_in_link(login_token)
        )
    if not settings.emails_enabled:
        return
    try:
        send_email(
            email_to=email_to,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    except Exception as e:
        logger.error(f"Sign-in email failed for {email_to}: {e}")
