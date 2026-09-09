"""keep_drop.drop_below(): must read the env var fresh each call, not cache it
at import — otherwise KEEP_DROP_PREFILTER_THRESHOLD can't disable the
pre-filter without a process restart.
"""

from __future__ import annotations

from pipeline import keep_drop


def test_drop_below_reflects_the_current_env_value(monkeypatch):
    monkeypatch.setenv("KEEP_DROP_PREFILTER_THRESHOLD", "0.42")
    assert keep_drop.drop_below() == 0.42

    monkeypatch.setenv("KEEP_DROP_PREFILTER_THRESHOLD", "0")
    assert keep_drop.drop_below() == 0.0


def test_drop_below_defaults_to_015_when_unset(monkeypatch):
    monkeypatch.delenv("KEEP_DROP_PREFILTER_THRESHOLD", raising=False)
    assert keep_drop.drop_below() == 0.15
