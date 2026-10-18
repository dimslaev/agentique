"""Email: rendering a template and handing the mail to Resend or SMTP.

The templates sit beside the feature that sends them.
"""

from __future__ import annotations

import html
import logging
import os
from pathlib import Path

import emails
import resend
from jinja2 import Template

from app.core.logging import log
from app.core.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def render_email_template(*, template: Path, context: dict[str, str | int]) -> str:
    return Template(template.read_text()).render(context)


def send_email(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    assert settings.emails_enabled, "no provided configuration for email variables"
    if settings.RESEND_API_KEY:
        resend.api_key = settings.RESEND_API_KEY
        response = resend.Emails.send(
            {
                "from": f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>",
                "to": email_to,
                "subject": subject,
                "html": html_content,
            }
        )
        logger.info(f"send email result: {response}")
        return
    assert settings.EMAILS_FROM_EMAIL  # For type checker
    message = emails.message.Message(
        subject=subject,
        html=html_content,
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
    )
    smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    elif settings.SMTP_SSL:
        smtp_options["ssl"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    response = message.send(to=email_to, smtp=smtp_options)
    logger.info(f"send email result: {response}")


def send_mail(subject_line: str, body: str) -> None:
    """Email through Resend, or log the mail when the environment has no key.
    Best-effort: a failed send is logged, never raised."""
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("EMAILS_FROM_EMAIL")
    to_email = os.environ.get("PIPELINE_ALERT_EMAIL") or from_email
    project = os.environ.get("PROJECT_NAME") or "Agentique"
    if not (api_key and from_email and to_email):
        log(f"  [mail suppressed — email env not set] {subject_line}\n{body}")
        return
    try:
        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": f"{project} pipeline <{from_email}>",
                "to": to_email,
                "subject": f"[{project}] {subject_line}",
                "html": f"<pre>{html.escape(body)}</pre>",
            }
        )
        log(f"  Mail sent to {to_email}: {subject_line}")
    except Exception as e:
        log(f"  Mail send failed: {e}")
