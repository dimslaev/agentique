from sqlmodel import Session

from app.models import (
    Article,
    ArticleCategory,
    ArticleKind,
    Category,
    Publisher,
    PublisherKind,
    slugify,
)
from tests.utils.utils import random_lower_string


def create_random_publisher(db: Session, **overrides: object) -> Publisher:
    name = random_lower_string()
    defaults: dict[str, object] = {
        "slug": slugify(name),
        "name": name,
        "kind": PublisherKind.community,
    }
    defaults.update(overrides)
    publisher = Publisher(**defaults)  # type: ignore[arg-type]
    db.add(publisher)
    db.commit()
    db.refresh(publisher)
    return publisher


def create_random_category(db: Session, **overrides: object) -> Category:
    name = random_lower_string()
    defaults: dict[str, object] = {
        "slug": slugify(name),
        "name": name,
        "description": random_lower_string(),
        "exemplars": [random_lower_string()],
    }
    defaults.update(overrides)
    category = Category(**defaults)  # type: ignore[arg-type]
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def create_random_article(db: Session, **overrides: object) -> Article:
    # every article needs a publisher; make one unless the caller supplied it
    if "publisher_id" not in overrides:
        overrides["publisher_id"] = create_random_publisher(db).id

    defaults: dict[str, object] = {
        "title": random_lower_string(),
        "url": f"https://example.com/{random_lower_string()}",
        "excerpt": random_lower_string(),
        "kind": ArticleKind.blog,
        "content": random_lower_string(),
    }
    defaults.update(overrides)
    article = Article(**defaults)  # type: ignore[arg-type]
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def categorize_article(db: Session, article: Article, category: Category) -> None:
    assert article.id is not None and category.id is not None
    db.add(ArticleCategory(article_id=article.id, category_id=category.id))
    db.commit()
