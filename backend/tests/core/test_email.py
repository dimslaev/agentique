"""The daily mail's send: suppressed without the env, never raising."""

from __future__ import annotations

import pytest
import resend

from app.core.email import send_mail


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    payloads: list[dict[str, str]] = []
    monkeypatch.setattr(resend.Emails, "send", payloads.append)
    return payloads


@pytest.fixture
def mail_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "key")
    monkeypatch.setenv("EMAILS_FROM_EMAIL", "pipeline@agentique.example")
    monkeypatch.setenv("PIPELINE_ALERT_EMAIL", "me@agentique.example")
    monkeypatch.setenv("PROJECT_NAME", "agentique")


def test_without_a_key_the_mail_is_logged_not_sent(
    monkeypatch: pytest.MonkeyPatch, sent: list[dict[str, str]]
) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    send_mail("Nothing landed", "body")
    assert sent == []


@pytest.mark.usefixtures("mail_env")
def test_the_mail_goes_to_the_alert_address_with_the_body_escaped(
    sent: list[dict[str, str]],
) -> None:
    send_mail("2 article(s) landed", "<b> & co")
    assert sent == [
        {
            "from": "agentique pipeline <pipeline@agentique.example>",
            "to": "me@agentique.example",
            "subject": "[agentique] 2 article(s) landed",
            "html": "<pre>&lt;b&gt; &amp; co</pre>",
        }
    ]


@pytest.mark.usefixtures("mail_env")
def test_a_failed_send_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_payload: dict[str, str]) -> None:
        raise RuntimeError("resend is down")

    monkeypatch.setattr(resend.Emails, "send", fail)
    send_mail("Pipeline needs a look", "body")
