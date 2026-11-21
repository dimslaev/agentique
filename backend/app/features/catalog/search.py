"""Article search by keyword.

What stays hidden is the mechanism: Postgres full-text over the title, summary,
content and tag names.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, literal_column, union_all
from sqlmodel import Session, col, select

from app.core.db.article import SEARCH_TSV, Article
from app.core.db.like import like_counts_subquery
from app.core.db.publisher import Publisher
from app.core.db.tag import ArticleTag, Tag
from app.features.catalog.model import ArticlesPublic
from app.features.catalog.rows import build_rows, filter_conditions, liked_article_ids

_MAX_LIMIT = 100
_EXCERPT_CAP = 300
# About `_EXCERPT_CAP` characters of plain text, with no markup around the match.
_HEADLINE_OPTIONS = 'StartSel="", StopSel="", MaxWords=45, MinWords=20'


def _excerpt(headline: str) -> str | None:
    return " ".join(headline.split())[:_EXCERPT_CAP] or None


def search(
    session: Session,
    q: str,
    limit: int = 20,
    *,
    viewer_id: uuid.UUID | None = None,
    tags: list[str] | None = None,
    kinds: list[str] | None = None,
    since: datetime | None = None,
    publisher: str | None = None,
) -> ArticlesPublic:
    """Articles matching `q` by keyword, best first.

    It looks for the keywords in the title, summary and content, and in the
    names of the article's tags. They all have to be in the text, or all in
    one tag.

    The filters narrow the articles before they are ranked. `tags` and `kinds`
    each match any of their values.

    Each article carries an excerpt of its content around the keywords, or its
    opening words when only the title matched.
    """
    conditions = filter_conditions(
        since=since, kinds=kinds, tags=tags, publisher=publisher
    )
    # The unstemmed query is for the title's unstemmed entries.
    tsquery = func.websearch_to_tsquery("english", q).op("||")(
        func.websearch_to_tsquery("simple", q)
    )
    # A tag is the curator's word for what the article is about, so it weighs
    # like the title. The slug is read too: `rag` is named "Retrieval &
    # Embeddings".
    tag_tsv = func.setweight(
        func.to_tsvector(
            "english", col(Tag.name) + " " + func.replace(col(Tag.slug), "-", " ")
        ),
        literal_column("'A'"),
    )
    tagged = (
        select(
            col(ArticleTag.article_id).label("id"),
            func.ts_rank(tag_tsv, tsquery).label("rank"),
        )
        .join(Tag, col(Tag.id) == col(ArticleTag.tag_id))
        .where(tag_tsv.op("@@")(tsquery))
        .subquery()
    )
    matches = union_all(
        select(
            col(Article.id).label("id"),
            func.ts_rank(SEARCH_TSV, tsquery).label("rank"),
        ).where(*conditions, SEARCH_TSV.op("@@")(tsquery)),
        select(col(Article.id).label("id"), tagged.c.rank)
        .join(tagged, tagged.c.id == col(Article.id))
        .where(*conditions),
    ).subquery()
    rank = func.sum(matches.c.rank)
    ranked = (
        select(matches.c.id, rank.label("rank"))
        .group_by(matches.c.id)
        .order_by(rank.desc(), matches.c.id.desc())
        .limit(min(limit, _MAX_LIMIT))
        .cte("ranked")
    )

    like_counts_subq = like_counts_subquery()
    like_count_expr = func.coalesce(like_counts_subq.c.like_count, 0)
    headline = func.ts_headline(
        "english", func.coalesce(col(Article.content), ""), tsquery, _HEADLINE_OPTIONS
    )
    statement = (
        select(Article, Publisher, like_count_expr.label("like_count"), headline)
        .join(ranked, ranked.c.id == col(Article.id))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(like_counts_subq, like_counts_subq.c.article_id == Article.id)
        .order_by(ranked.c.rank.desc(), col(Article.id).desc())
    )

    rows = session.exec(statement).all()
    liked_ids = liked_article_ids(session, viewer_id) if viewer_id else set()
    data = build_rows(session, [(a, p, likes) for a, p, likes, _ in rows], liked_ids)
    for article, (_, _, _, text) in zip(data, rows, strict=True):
        article.excerpt = _excerpt(text)
    return ArticlesPublic(data=data, count=len(data))
