"""Creates the first superuser on a fresh database."""

from __future__ import annotations

import logging

from sqlmodel import Session

from app.audience.service import init_db
from app.platform.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    with Session(engine) as session:
        init_db(session)


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
