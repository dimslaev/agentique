"""The `queue_candidate` tool: an unseen URL becomes a pending candidate with
what the curation agent reads, and every refusal leaves the ledger alone."""

from __future__ import annotations

from collections.abc import Callable, Generator

import pytest
from fastmcp.exceptions import ToolError
from sqlmodel import Session, col, delete, select

from app.core.db.article import Article
from app.core.db.factories import create_random_article, random_lower_string
from app.core.db.ledger import Reject, RejectStage
from app.core.db.publisher import LinkPlatform, Publisher, PublisherKind
from app.core.extract import EMPTY_PAGE, Page
from app.entry.mcp.queue_candidate import queue_candidate

BODY = "A measured look at agent harnesses. " * 20
FETCH = "app.features.collect.submit.fetch_page"
THIN_REPO = "app.features.collect.filter.repo_for"


@pytest.fixture
def fetched(monkeypatch: pytest.MonkeyPatch) -> Callable[[Page], list[str]]:
    """Stub the page fetch with ``page``; returns the URLs it was asked for."""
    asked: list[str] = []

    def stub(page: Page) -> list[str]:
        def fetch(url: str, *_: object, **__: object) -> Page:
            asked.append(url)
            return page

        monkeypatch.setattr(FETCH, fetch)
        return asked

    return stub


GOOD_PAGE = Page(BODY, {}, "Harnesses, measured", "2026-11-19")


@pytest.fixture
def url(db: Session) -> Generator[str]:
    """A fresh URL on a fresh host; its publisher and ledger row are removed."""
    host = f"{random_lower_string()}.example"
    link = f"https://{host}/posts/one"
    yield link
    db.rollback()
    db.exec(delete(Reject).where(col(Reject.url) == link))
    db.exec(delete(Publisher).where(col(Publisher.slug) == host.replace(".", "-")))
    db.commit()


def _row(db: Session, link: str) -> Reject | None:
    db.expire_all()
    return db.get(Reject, link)


def test_an_unseen_url_is_queued_as_a_pending_candidate(
    db: Session, url: str, fetched: Callable[[Page], list[str]]
) -> None:
    asked = fetched(GOOD_PAGE)
    result = queue_candidate(url, "AINews top story 2026-11-19")

    assert result == f"Queued {url}: Harnesses, measured"
    assert asked == [url]
    row = _row(db, url)
    assert row is not None
    assert row.stage == RejectStage.pending
    assert row.title == "Harnesses, measured"
    assert row.content == BODY
    assert row.source == "Competitor watch"
    assert row.traction == "AINews top story 2026-11-19"
    assert row.published_at is not None
    assert row.published_at.date().isoformat() == "2026-11-19"
    publisher = db.get(Publisher, row.publisher_id)
    assert publisher is not None
    assert publisher.is_active is False
    assert publisher.kind == PublisherKind.unknown


def test_a_site_we_carry_is_credited_to_its_publisher(
    db: Session, url: str, fetched: Callable[[Page], list[str]]
) -> None:
    host = url.split("/")[2]
    publisher = Publisher(
        slug=host.replace(".", "-"),
        name="Known Lab",
        kind=PublisherKind.lab,
        links={LinkPlatform.website: f"https://{host}"},
    )
    db.add(publisher)
    db.commit()
    fetched(GOOD_PAGE)

    queue_candidate(url, "AINews top story")
    row = _row(db, url)
    assert row is not None and row.publisher_id == publisher.id


def test_a_page_with_no_date_is_still_queued(
    db: Session, url: str, fetched: Callable[[Page], list[str]]
) -> None:
    fetched(Page(BODY, {}, "Harnesses, measured", None))
    queue_candidate(url, "AINews top story")
    row = _row(db, url)
    assert row is not None and row.published_at is None


def test_an_article_is_refused(
    db: Session, made: dict[str, list[int]], fetched: Callable[[Page], list[str]]
) -> None:
    asked = fetched(GOOD_PAGE)
    article = create_random_article(db)
    assert article.id is not None
    made["articles"].append(article.id)
    made["publishers"].append(article.publisher_id)

    with pytest.raises(ToolError, match="already known"):
        queue_candidate(article.url, "AINews top story")
    # The trailing-slash variant is the same URL, as in the nightly run.
    with pytest.raises(ToolError, match="already known"):
        queue_candidate(article.url + "/", "AINews top story")
    assert asked == []
    assert db.exec(select(Article).where(col(Article.url) == article.url)).one()


@pytest.mark.parametrize(
    "stage", [RejectStage.pending, RejectStage.below_threshold, RejectStage.duplicate]
)
def test_a_url_in_the_ledger_is_refused_whatever_its_stage(
    db: Session, url: str, stage: RejectStage, fetched: Callable[[Page], list[str]]
) -> None:
    asked = fetched(GOOD_PAGE)
    db.add(Reject(url=url, stage=stage, title="Seen", reason="r"))
    db.commit()

    with pytest.raises(ToolError, match="already known"):
        queue_candidate(url, "AINews top story")
    assert asked == []
    row = _row(db, url)
    assert row is not None and row.title == "Seen" and row.stage == stage


@pytest.mark.parametrize("reason", ["", "  "])
def test_a_blank_reason_is_refused(reason: str, url: str) -> None:
    with pytest.raises(ToolError, match="reason"):
        queue_candidate(url, reason)


@pytest.mark.parametrize("link", ["", "not a url", "ftp://never-queued.example/x"])
def test_a_url_that_is_not_http_is_refused(link: str) -> None:
    with pytest.raises(ToolError, match="not an http"):
        queue_candidate(link, "AINews top story")


def test_an_event_or_reference_page_is_refused(
    db: Session, fetched: Callable[[Page], list[str]]
) -> None:
    asked = fetched(GOOD_PAGE)
    for link in (
        "https://luma.com/never-queued-event",
        "https://never-queued.example/docs/models",
    ):
        with pytest.raises(ToolError, match="event or reference page"):
            queue_candidate(link, "AINews top story")
        assert _row(db, link) is None
    assert asked == []


def test_a_page_with_no_readable_text_is_refused(
    db: Session, url: str, fetched: Callable[[Page], list[str]]
) -> None:
    fetched(EMPTY_PAGE)
    with pytest.raises(ToolError, match="No readable text"):
        queue_candidate(url, "AINews top story")
    assert _row(db, url) is None


def test_a_teaser_is_refused_like_the_nightly_run_drops_it(
    db: Session, url: str, fetched: Callable[[Page], list[str]]
) -> None:
    fetched(Page("Too short to summarize.", {}, "Teaser", None))
    with pytest.raises(ToolError, match="No readable text"):
        queue_candidate(url, "AINews top story")
    assert _row(db, url) is None


def test_a_page_with_no_title_is_refused(
    db: Session, url: str, fetched: Callable[[Page], list[str]]
) -> None:
    fetched(Page(BODY, {}, "", "2026-11-19"))
    with pytest.raises(ToolError, match="No title"):
        queue_candidate(url, "AINews top story")
    assert _row(db, url) is None


def test_a_shared_host_with_no_author_is_refused_and_makes_no_publisher(
    db: Session, fetched: Callable[[Page], list[str]]
) -> None:
    fetched(GOOD_PAGE)
    link = "https://www.reddit.com/r/LocalLLaMA/comments/never-queued"
    with pytest.raises(ToolError, match="names no publisher"):
        queue_candidate(link, "AINews top story")
    assert _row(db, link) is None
    db.expire_all()
    assert (
        db.exec(select(Publisher).where(col(Publisher.slug) == "reddit-com")).first()
        is None
    )


def test_a_thin_repo_is_refused_and_recorded_like_the_nightly_run_does(
    db: Session,
    made: dict[str, list[int]],
    monkeypatch: pytest.MonkeyPatch,
    fetched: Callable[[Page], list[str]],
) -> None:
    owner = random_lower_string()
    publisher = Publisher(
        slug=owner,
        name=owner,
        kind=PublisherKind.individual,
        links={LinkPlatform.github: f"https://github.com/{owner}"},
    )
    db.add(publisher)
    db.commit()
    assert publisher.id is not None
    made["publishers"].append(publisher.id)
    fetched(GOOD_PAGE)
    monkeypatch.setattr(THIN_REPO, lambda *_: {"stargazers_count": 3})
    link = f"https://github.com/{owner}/tiny"

    try:
        with pytest.raises(ToolError, match="star floor"):
            queue_candidate(link, "AINews top story")
        row = _row(db, link)
        assert row is not None and row.stage == RejectStage.thin_repo
    finally:
        db.exec(delete(Reject).where(col(Reject.url) == link))
        db.commit()
