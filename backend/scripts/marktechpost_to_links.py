"""Replace MarkTechPost's published articles with the links they cover (ADR 22).

For each article: fetch the post, queue its first outside link as a candidate
the way the feed now does, then delete the article with its tags, likes and
story links. Its URL goes in the reject ledger so it never comes back as a
candidate. An article whose page does not load is left for the next run. The
curation agent judges the queued links on its next session, so an article that
was the only copy of a story is back once its link is approved.

Dry run by default. From `backend/`:
`uv run python scripts/marktechpost_to_links.py [--apply]`
"""

from __future__ import annotations

import sys

from sqlmodel import Session, col, delete, select

from app.core.db.article import Article
from app.core.db.engine import engine
from app.core.db.ledger import RejectStage, record_reject
from app.core.db.like import ArticleLike
from app.core.db.publisher import Publisher
from app.core.db.story import StoryArticle
from app.core.db.tag import ArticleTag
from app.core.extract import fetch_full_content
from app.features.collect.feeds import linked_items
from app.features.collect.fetch import resolve_publishers
from app.features.collect.filter import filter_known_urls
from app.features.collect.model import RawItem
from app.features.collect.publishers import PublisherResolver
from app.features.collect.queue import queue_candidates

SLUG = "marktechpost"
REASON = "aggregator retelling, replaced by the links it covers (ADR 22)"


def main(apply: bool) -> None:
    with Session(engine) as session:
        publisher = session.exec(select(Publisher).where(Publisher.slug == SLUG)).one()
        assert publisher.id is not None
        articles = session.exec(
            select(Article).where(Article.publisher_id == publisher.id)
        ).all()
        ids = [a.id for a in articles]
        likes = session.exec(
            select(ArticleLike).where(col(ArticleLike.article_id).in_(ids))
        ).all()
        stories = session.exec(
            select(StoryArticle).where(col(StoryArticle.article_id).in_(ids))
        ).all()
        print(
            f"{len(articles)} articles, {len(likes)} likes, {len(stories)} story links"
        )

        pages = fetch_full_content([a.url for a in articles])
        # An article whose page did not load is kept for a rerun: deleting it
        # would drop its story with nothing queued in its place.
        unread = [a.url for a in articles if a.url not in pages]
        articles = [a for a in articles if a.url in pages]
        ids = [a.id for a in articles]
        posts: list[RawItem] = [
            {
                "title": a.title,
                "url": a.url,
                "content": "",
                "published_date": a.published_at.isoformat()
                if a.published_at
                else None,
                "source": publisher.name,
                "links": pages[a.url].links,
            }
            for a in articles
        ]
        for post in posts:
            if not post.get("links"):
                print(f"  no links: {post['url']}")
        links = filter_known_urls(
            session, [i for post in posts for i in linked_items(post)], SLUG
        )
        links = list({i["url"]: i for i in links}.values())
        for i in links:
            print(f"  queue {i['url']}  <- {i['title'][:60]}")
        print(f"{len(links)} links to queue")
        print(
            f"{len(articles)} articles to delete, {len(unread)} kept: page did not load"
        )

        if not apply:
            print("Dry run. Pass --apply to queue and delete.")
            return

        queue_candidates(
            session, resolve_publishers(links, PublisherResolver(session=session))
        )
        for table in (ArticleTag, ArticleLike, StoryArticle):
            session.exec(delete(table).where(col(table.article_id).in_(ids)))
        for a, post in zip(articles, posts, strict=True):
            record_reject(
                session,
                {**post, "publisher_id": publisher.id},
                RejectStage.below_threshold,
                score=a.score,
                reason=REASON,
            )
            session.delete(a)
        session.commit()
        print(f"Queued {len(links)} links, deleted {len(articles)} articles")
        if unread:
            print(f"{len(unread)} pages did not load. Run again to finish.")


if __name__ == "__main__":
    main("--apply" in sys.argv)
