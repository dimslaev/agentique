"""The `reject_articles` tool: turn one or more candidates down, each on its own."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.features.curation import service as curation
from app.features.curation.model import Verdict


def reject_articles(verdicts: list[Verdict]) -> str:
    """Turn down one or more candidates, keeping the score and the reason for
    each: `verdicts` is a list of `{url, score, reason}`.

    The row is kept as a past decision so the URL is never judged twice, and so the
    verdicts can be read back as labels. Write `reason` for a human reading a
    hundred of them later, not for a log line. Each is settled on its own, so one URL that is not pending costs that line
    and not the batch. Returns one line per verdict, in order, saying whether
    it was rejected or why not.
    """
    with Session(engine) as session:
        return "\n".join(curation.reject_articles(session, verdicts))
