"""Tests for the DB-readiness wait that gates startup and the test suite."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlmodel import select

from scripts.wait_for_db import init, logger


def test_init_successful_connection() -> None:
    engine_mock = MagicMock()

    session_mock = MagicMock()
    session_mock.__enter__.return_value = session_mock

    select1 = select(1)

    with (
        patch("scripts.wait_for_db.Session", return_value=session_mock),
        patch("scripts.wait_for_db.select", return_value=select1),
        patch.object(logger, "info"),
        patch.object(logger, "error"),
        patch.object(logger, "warn"),
    ):
        try:
            init(engine_mock)
            connection_successful = True
        except Exception:
            connection_successful = False

        assert connection_successful, (
            "The database connection should be successful and not raise an exception."
        )

        session_mock.exec.assert_called_once_with(select1)
