import logging
import math
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models import (
    Article,
    ArticleCategory,
    ArticleKind,
    Category,
    Publisher,
    PublisherKind,
    TrustLevel,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fixed seed so local dev, CI, and the Playwright stack all get the same 50 rows.
SEED = 20260701

KINDS = list(ArticleKind)

EMBEDDING_DIM = 256
ARTICLE_COUNT = 50

# Mirrors the real publisher mix: a couple of companies, a community aggregator,
# and some individual/media newsletters.
SAMPLE_PUBLISHERS = [
    ("ai-news", "AI News", PublisherKind.media, TrustLevel.medium),
    ("hacker-news", "Hacker News", PublisherKind.community, TrustLevel.medium),
    ("the-batch", "The Batch", PublisherKind.media, TrustLevel.high),
    ("import-ai", "Import AI", PublisherKind.individual, TrustLevel.high),
    ("latent-space", "Latent Space", PublisherKind.individual, TrustLevel.medium),
]


def _normalized_embedding(rng: random.Random) -> list[float]:
    vec = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


def _published_at(rng: random.Random, index: int) -> datetime:
    now = datetime.now(UTC)
    if index < 40:
        # bulk: today down to a week ago
        return now - timedelta(days=rng.uniform(0, 7))
    elif index < 48:
        # a week ago down to a month ago
        return now - timedelta(days=rng.uniform(7, 30))
    else:
        # older still, to exercise deeper date filters
        return now - timedelta(days=rng.uniform(31, 40))


def make_sample_publishers() -> list[Publisher]:
    return [
        Publisher(
            slug=slug,
            name=name,
            kind=kind,
            trust=trust,
            description=f"{name} — sample publisher.",
            image=f"https://example.com/publishers/{slug}.png",
            links={},
        )
        for slug, name, kind, trust in SAMPLE_PUBLISHERS
    ]


def make_sample_articles(publisher_ids: list[int]) -> list[Article]:
    rng = random.Random(SEED)
    articles = []
    for i in range(ARTICLE_COUNT):
        articles.append(
            Article(
                title=f"Sample article {i + 1}",
                publisher_id=rng.choice(publisher_ids),
                url=f"https://example.com/articles/{i + 1}",
                published_at=_published_at(rng, i),
                excerpt=f"Excerpt for sample article {i + 1}.",
                kind=rng.choice(KINDS),
                content=f"Content body for sample article {i + 1}.",
                embedding=_normalized_embedding(rng),
            )
        )
    return articles


def make_sample_article_categories(
    article_ids: list[int], category_ids: list[int]
) -> list[ArticleCategory]:
    """1-3 categories per article, drawn from whatever `seed_categories` loaded.

    Every sample article gets at least one, matching the real invariant: an
    article with no category is never stored.
    """
    if not category_ids:
        return []
    rng = random.Random(SEED)
    return [
        ArticleCategory(article_id=article_id, category_id=category_id)
        for article_id in article_ids
        for category_id in rng.sample(
            category_ids, k=min(rng.randint(1, 3), len(category_ids))
        )
    ]


def seed(session: Session) -> None:
    # Only ever populate an empty table. prestart runs this on every stack start,
    # and a local DB loaded from the real dump must survive that.
    existing = session.exec(select(func.count()).select_from(Article)).one()
    if existing:
        logger.info("%s articles already present, skipping seed", existing)
        return

    publishers = make_sample_publishers()
    session.add_all(publishers)
    session.commit()
    publisher_ids = [p.id for p in publishers if p.id is not None]

    articles = make_sample_articles(publisher_ids)
    session.add_all(articles)
    session.commit()
    article_ids = [a.id for a in articles if a.id is not None]

    category_ids = [
        c.id for c in session.exec(select(Category)).all() if c.id is not None
    ]
    session.add_all(make_sample_article_categories(article_ids, category_ids))
    session.commit()


def main() -> None:
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "Refusing to run seed_articles in production; it inserts sample data."
        )
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    main()
