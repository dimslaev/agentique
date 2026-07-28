"""Step 4: insert the articles that matched a category.

Everything an article carries is settled here — categories, excerpt, format.
There is no LLM pass after insert any more except the title rewrite, so a row
is complete the moment it exists.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models import Article, ArticleKind
from pipeline.categories import (
    MAX_CATEGORIES_PER_ARTICLE,
    Vocabulary,
    write_article_categories,
)
from pipeline.excerpt import to_excerpt
from pipeline.heuristics import github_repo_from_content, kind_from_url
from pipeline.llm_text import sanitize_llm_text
from pipeline.types import FetchedArticle
from pipeline.utils import enum_value, log, parse_date


def best_per_url(matched: list[FetchedArticle]) -> list[FetchedArticle]:
    """One article per URL, merging their categories. Pure: no I/O.

    Two sources can surface the same URL in one run (an HN post and a feed item
    for the same post); the URL is the identity. There is no score to break the
    tie any more, so the first occurrence wins on content and the categories are
    unioned — both judgements were made about the same article, and dropping one
    would lose a lane for no reason. The union is capped the same way a single
    match is.
    """
    by_url: dict[str, FetchedArticle] = {}
    for item in matched:
        existing = by_url.get(item["url"])
        if not existing:
            # Copied, not aliased: the union below writes back into this dict,
            # and a step must not mutate the list it was handed.
            by_url[item["url"]] = {**item}
            continue
        merged = list(existing.get("categories", []))
        for slug in item.get("categories", []):
            if slug not in merged:
                merged.append(slug)
        existing["categories"] = merged[:MAX_CATEGORIES_PER_ARTICLE]
    return list(by_url.values())


def resolve_kind(url: str, content: str, hint: str | None) -> ArticleKind:
    """The article's format.

    The URL host wins when it is conclusive — a github.com link is a repo, and
    no model gets a vote on that. Otherwise take the matcher's hint, and fall
    back to blog. A blog-looking post that links a repo is a repo.
    """
    from_url = kind_from_url(url)
    if from_url:
        return from_url

    kind = ArticleKind.blog
    if hint:
        try:
            kind = ArticleKind(enum_value(hint).lower())
        except ValueError:
            log(f"  Dropped unknown kind {hint!r}")
    if kind == ArticleKind.blog and github_repo_from_content(content):
        return ArticleKind.repo
    return kind


def insert_articles(
    session: Session, matched: list[FetchedArticle], vocab: Vocabulary
) -> list[FetchedArticle]:
    if not matched:
        return []

    inserted: list[FetchedArticle] = []
    for item in best_per_url(matched):
        title = sanitize_llm_text(item["title"])
        content = sanitize_llm_text(item.get("content") or "")
        article = Article(
            title=title,
            publisher_id=item["publisher_id"],
            url=item["url"],
            published_at=parse_date(item.get("published_date")),
            # Deterministic, computed from the content we already have. This
            # used to be an LLM summary written in a later step; see
            # pipeline/excerpt.py for why it is not any more.
            excerpt=to_excerpt(content),
            kind=resolve_kind(item["url"], content, item.get("kind_hint")),
            content=content,
        )
        session.add(article)
        session.flush()
        assert article.id is not None

        # Written here rather than in enrich: the categories are the reason the
        # article was admitted, so a row must never exist without them.
        write_article_categories(session, article.id, item["categories"], vocab)

        log(f"  Inserted #{article.id}: [{', '.join(item['categories'])}] {title}")
        inserted.append(
            {
                **item,
                "id": article.id,
                "title": title,
                "content": content,
                "excerpt": article.excerpt,
            }
        )

    session.commit()
    return inserted
