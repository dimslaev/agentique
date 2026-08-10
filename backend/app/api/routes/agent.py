"""The curation agent's tool API.

Everything the agent can do lives here. It reads widely — feed items,
publishers, tags, and arbitrary SELECT — because a bad read costs nothing, and
it writes only through typed endpoints, because one confused `sql_write` drops
the table. There is no `sql_write` and there will not be one.

The whole router sits behind a single bearer token (`AGENT_API_TOKEN`) and
fails closed when it is unset. See `agent/CLAUDE.md` for the agent's side of
this contract.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import DatabaseError
from sqlmodel import col, func, select
from starlette.concurrency import run_in_threadpool

from app.api.deps import AgentAuth, SessionDep
from app.core.config import settings
from app.embedding import embed, embedding_text
from app.models import (
    AgentArticleCreate,
    AgentArticleCreated,
    AgentPublisher,
    AgentTag,
    Article,
    ArticleTag,
    FeedItem,
    FeedItemDecision,
    FeedItemPublic,
    FeedItemsPublic,
    FeedItemStatus,
    FetchUrlRequest,
    FetchUrlResult,
    Publisher,
    PublisherUpsert,
    SqlReadRequest,
    SqlReadResult,
    Tag,
    TagCreate,
    slugify,
)
from pipeline.sources.extract_content import fetch_and_extract

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[AgentAuth])

# Same cap the LLM pipeline applied: three tags that mean something beat five
# that nearly do, and the tag filters in the sidebar get noisy past three.
MAX_TAGS_PER_ARTICLE = 3
# Extracted text returned by fetch_url. Past this an article is a book, and the
# agent is judging it, not reading it end to end.
MAX_FETCH_CHARS = 40_000


# ─── Feed items ─────────────────────────────────────────────────────────────


def _feed_item_public(
    item: FeedItem, publisher_names: dict[int, str], content_chars: int
) -> FeedItemPublic:
    content = item.content or ""
    truncated = len(content) > content_chars
    return FeedItemPublic(
        id=item.id or 0,
        url=item.url,
        title=item.title,
        content=content[:content_chars] or None,
        content_truncated=truncated,
        published_at=item.published_at,
        feed_publisher_id=item.feed_publisher_id,
        feed_publisher=publisher_names.get(item.feed_publisher_id or 0),
        links=item.links,
        fetched_at=item.fetched_at,
        status=item.status,
        decision=item.decision,
    )


@router.get("/feed-items", response_model=FeedItemsPublic)
def list_feed_items(
    session: SessionDep,
    status: FeedItemStatus = FeedItemStatus.new,
    limit: int = Query(default=10, ge=1, le=100),
    content_chars: int = Query(default=2000, ge=0, le=50_000),
) -> Any:
    """The inbox, newest first. `count` is every item in that status, not just
    the ones on this page — it is how the agent knows how much is left."""
    condition = col(FeedItem.status) == status
    count = session.exec(
        select(func.count()).select_from(FeedItem).where(condition)
    ).one()
    items = session.exec(
        select(FeedItem)
        .where(condition)
        .order_by(col(FeedItem.fetched_at).desc(), col(FeedItem.id).desc())
        .limit(limit)
    ).all()

    publisher_ids = {i.feed_publisher_id for i in items if i.feed_publisher_id}
    names: dict[int, str] = {}
    if publisher_ids:
        rows = session.exec(
            select(Publisher.id, Publisher.name).where(
                col(Publisher.id).in_(publisher_ids)
            )
        ).all()
        names = {pid: name for pid, name in rows if pid is not None}

    return FeedItemsPublic(
        data=[_feed_item_public(i, names, content_chars) for i in items],
        count=count,
    )


@router.post("/feed-items/{item_id}/decision", response_model=FeedItemPublic)
def mark_feed_item(item_id: int, body: FeedItemDecision, session: SessionDep) -> Any:
    """Record the agent's verdict. Decided items never come back in a `new`
    batch, which is what makes a half-finished run safe to just re-run."""
    if body.status == FeedItemStatus.new:
        raise HTTPException(
            status_code=422, detail="A decision must be 'accepted' or 'rejected'"
        )

    item = session.get(FeedItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"No feed item {item_id}")

    item.status = body.status
    item.decision = body.decision
    item.decided_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)

    names: dict[int, str] = {}
    if item.feed_publisher_id:
        publisher = session.get(Publisher, item.feed_publisher_id)
        if publisher is not None:
            names[item.feed_publisher_id] = publisher.name
    return _feed_item_public(item, names, MAX_FETCH_CHARS)


# ─── Publishers and tags ────────────────────────────────────────────────────


def _agent_publisher(publisher: Publisher) -> AgentPublisher:
    return AgentPublisher(
        id=publisher.id or 0,
        slug=publisher.slug,
        name=publisher.name,
        kind=publisher.kind,
        type=publisher.type,
        trust=publisher.trust,
        is_active=publisher.is_active,
        description=publisher.description,
        links=publisher.links or {},
    )


@router.get("/publishers", response_model=list[AgentPublisher])
def list_publishers(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> Any:
    statement = select(Publisher).order_by(col(Publisher.name))
    if q:
        statement = statement.where(
            col(Publisher.name).ilike(f"%{q}%") | col(Publisher.slug).ilike(f"%{q}%")
        )
    return [_agent_publisher(p) for p in session.exec(statement.limit(limit)).all()]


@router.post("/publishers", response_model=AgentPublisher)
def upsert_publisher(body: PublisherUpsert, session: SessionDep) -> Any:
    """Create or update a publisher by slug.

    This is how a first-party source the agent found mid-run becomes an
    attribution target. Leave the links empty and the pipeline never polls it —
    it exists only so the article has the right byline.
    """
    slug = slugify(body.slug or body.name)
    if not slug:
        raise HTTPException(status_code=422, detail="slug must not be empty")

    publisher = session.exec(select(Publisher).where(Publisher.slug == slug)).first()
    if publisher is None:
        publisher = Publisher(slug=slug, name=body.name, kind=body.kind)

    publisher.name = body.name
    publisher.kind = body.kind
    publisher.type = body.type
    publisher.description = body.description
    publisher.image = body.image
    publisher.links = body.links
    publisher.trust = body.trust
    publisher.is_active = body.is_active

    session.add(publisher)
    session.commit()
    session.refresh(publisher)
    return _agent_publisher(publisher)


@router.get("/tags", response_model=list[AgentTag])
def list_tags(session: SessionDep) -> Any:
    """The whole controlled vocabulary — slug, name, and when to apply it."""
    tags = session.exec(select(Tag).order_by(col(Tag.slug))).all()
    return [
        AgentTag(id=t.id or 0, slug=t.slug, name=t.name, description=t.description)
        for t in tags
    ]


@router.post("/tags", response_model=AgentTag)
def create_tag(body: TagCreate, session: SessionDep) -> Any:
    """Mint a vocabulary entry. Rare by design: a tag that fits three articles
    a year is a worse filter than no tag."""
    slug = slugify(body.slug or body.name)
    if not slug:
        raise HTTPException(status_code=422, detail="slug must not be empty")
    if session.exec(select(Tag).where(Tag.slug == slug)).first():
        raise HTTPException(status_code=409, detail=f"Tag {slug!r} already exists")

    tag = Tag(slug=slug, name=body.name, description=body.description)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return AgentTag(
        id=tag.id or 0, slug=tag.slug, name=tag.name, description=tag.description
    )


# ─── Arbitrary reads ────────────────────────────────────────────────────────

_READ_STATEMENT = re.compile(r"^(select|with)\b", re.IGNORECASE)

_readonly_engine: Engine | None = None


def get_readonly_engine() -> Engine:  # pragma: no cover
    global _readonly_engine
    if _readonly_engine is None:
        uri = settings.AGENT_READONLY_DATABASE_URI or str(
            settings.SQLALCHEMY_DATABASE_URI
        )
        _readonly_engine = create_engine(uri, pool_pre_ping=True, pool_size=2)
    return _readonly_engine


def validate_select(query: str) -> str:
    """Normalise a query, or raise 422. Pure, so it is cheap to pin in tests.

    Three cheap gates in front of the read-only role, not instead of it: one
    statement, and that statement reads. The role is what actually stops a
    write; this is what stops a confusing error message.
    """
    normalised = query.strip().rstrip(";").strip()
    if not normalised:
        raise HTTPException(status_code=422, detail="query must not be empty")
    if ";" in normalised:
        raise HTTPException(
            status_code=422, detail="One statement per call; ';' is not allowed"
        )
    if not _READ_STATEMENT.match(normalised):
        raise HTTPException(
            status_code=422, detail="Only SELECT and WITH queries are allowed"
        )
    return normalised


def _json_safe(value: Any) -> Any:
    """Anything psycopg hands back, as something JSON can carry.

    Vectors, intervals and the odd custom type have no JSON form; stringifying
    them beats failing the whole query over one column the agent probably did
    not mean to select.
    """
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list | dict):
        return value
    return str(value)


@router.post("/sql", response_model=SqlReadResult)
def sql_read(body: SqlReadRequest) -> Any:
    """Run one SELECT and return its rows.

    Open on purpose: the agent asking "what have we published from this
    publisher lately?" should not need a new endpoint every time it thinks of
    a new question. Bounded by a read-only transaction, a statement timeout,
    and a row cap.
    """
    query = validate_select(body.query)
    cap = min(body.limit or settings.AGENT_SQL_ROW_CAP, settings.AGENT_SQL_ROW_CAP)

    engine = get_readonly_engine()
    with engine.connect() as conn:
        try:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql(
                f"SET LOCAL statement_timeout = {int(settings.AGENT_SQL_TIMEOUT_MS)}"
            )
            result = conn.exec_driver_sql(query)
            columns = list(result.keys())
            rows = result.fetchmany(cap + 1)
        except DatabaseError as e:
            # The agent wrote the query, so it is the one that can fix it —
            # hand back what postgres said rather than a bare 500.
            raise HTTPException(status_code=400, detail=str(e.orig or e))
        finally:
            conn.rollback()

    truncated = len(rows) > cap
    kept = rows[:cap]
    return SqlReadResult(
        columns=columns,
        rows=[[_json_safe(v) for v in row] for row in kept],
        row_count=len(kept),
        truncated=truncated,
    )


# ─── Fetching ───────────────────────────────────────────────────────────────

# fetch_url shares a process with the site. Without a cap, one batch of the
# agent's fetches (up to 20s each on the proxied path) starves page requests.
_fetch_slots = asyncio.Semaphore(settings.AGENT_FETCH_CONCURRENCY)


def validate_fetch_url(raw: str) -> str:
    """Reject anything that is not an ordinary public http(s) URL.

    The URLs reaching this endpoint came out of feed content the agent read, so
    they are attacker-influenced. This blocks the obvious internal targets; it
    is not a complete SSRF defence (a public hostname resolving inward still
    gets through), which is the other reason the fetch runs with no credentials
    and returns only extracted text.
    """
    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Expected an http(s) URL")

    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise HTTPException(status_code=422, detail="Refusing to fetch a local address")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return raw.strip()
    if not ip.is_global:
        raise HTTPException(status_code=422, detail="Refusing to fetch a local address")
    return raw.strip()


@router.post("/fetch-url", response_model=FetchUrlResult)
async def fetch_url(body: FetchUrlRequest) -> Any:
    """Fetch one URL and return its readable text.

    Direct first, residential proxy on failure, trafilatura for the extract —
    the same path the pipeline uses on its own sources. An empty result is an
    answer, not an error: plenty of pages will not give us text, and the agent
    still has the title to judge on.
    """
    url = validate_fetch_url(body.url)

    try:
        await asyncio.wait_for(
            _fetch_slots.acquire(), timeout=settings.AGENT_FETCH_QUEUE_SECONDS
        )
    except TimeoutError:
        raise HTTPException(
            status_code=503, detail="fetch_url is saturated, retry shortly"
        )
    try:
        text = await run_in_threadpool(fetch_and_extract, url)
    finally:
        _fetch_slots.release()

    truncated = len(text) > MAX_FETCH_CHARS
    return FetchUrlResult(
        url=url,
        ok=bool(text),
        chars=len(text),
        text=text[:MAX_FETCH_CHARS],
        truncated=truncated,
    )


# ─── Writing an article ─────────────────────────────────────────────────────


def _embed(text: str) -> list[float]:  # pragma: no cover
    """Indirection kept so tests can swap the real model out by name."""
    return embed(text)


@router.post("/articles", response_model=AgentArticleCreated)
def create_article(body: AgentArticleCreate, session: SessionDep) -> Any:
    """Publish one article.

    The agent never sends a vector and never sends SQL: it sends the fields it
    judged, and this validates them, embeds server-side, inserts, and links the
    tags. A duplicate URL is a 409 rather than a second row.
    """
    url = body.url.strip()
    title = body.title.strip()
    if not url or not title:
        raise HTTPException(status_code=422, detail="url and title are required")
    if session.exec(select(Article).where(Article.url == url)).first():
        raise HTTPException(status_code=409, detail=f"Already published: {url}")

    publisher = session.exec(
        select(Publisher).where(Publisher.slug == body.publisher_slug)
    ).first()
    if publisher is None or publisher.id is None:
        raise HTTPException(
            status_code=422,
            detail=f"No publisher with slug {body.publisher_slug!r} — create it first",
        )

    slugs = list(dict.fromkeys(body.tags))
    if len(slugs) > MAX_TAGS_PER_ARTICLE:
        raise HTTPException(
            status_code=422, detail=f"At most {MAX_TAGS_PER_ARTICLE} tags per article"
        )
    tags = (
        session.exec(select(Tag).where(col(Tag.slug).in_(slugs))).all() if slugs else []
    )
    unknown = set(slugs) - {t.slug for t in tags}
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown tag slug(s): {', '.join(sorted(unknown))}",
        )

    article = Article(
        title=title,
        url=url,
        publisher_id=publisher.id,
        # A null published_at drops the article out of every date-filtered
        # read, which is most of the site — so it gets a real timestamp.
        published_at=body.published_at or datetime.now(UTC),
        score=body.score,
        kind=body.kind,
        categories=list(dict.fromkeys(body.categories)),
        summary=body.summary,
        content=body.content,
    )
    try:
        article.embedding = _embed(embedding_text(title, body.content))
    except Exception:
        # Best-effort, same as the pipeline's embed step: an article with no
        # vector is invisible to search, which is worse than no article only if
        # you also lose the article.
        article.embedding = None

    session.add(article)
    session.commit()
    session.refresh(article)
    assert article.id is not None

    for tag in tags:
        assert tag.id is not None
        session.add(ArticleTag(article_id=article.id, tag_id=tag.id))
    if tags:
        session.commit()

    return AgentArticleCreated(
        id=article.id,
        url=article.url,
        title=article.title,
        score=article.score,
        publisher_slug=publisher.slug,
        tags=[t.slug for t in tags],
        embedded=article.embedding is not None,
    )
