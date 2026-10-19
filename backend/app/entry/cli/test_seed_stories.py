"""The sample stories seed, which must never run against production."""

from __future__ import annotations

import pytest

from app.core.settings import settings
from app.entry.cli import seed_stories


def test_the_seed_refuses_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises((RuntimeError, SystemExit), match="Refusing"):
        seed_stories.main()
