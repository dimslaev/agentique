import random

from sqlmodel import Session

from app.models import (
    Article,
    ArticleKind,
    ArticleTag,
    Publisher,
    PublisherKind,
    Tag,
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


def create_random_tag(db: Session, **overrides: object) -> Tag:
    name = random_lower_string()
    defaults: dict[str, object] = {
        "slug": slugify(name),
        "name": name,
        "description": random_lower_string(),
    }
    defaults.update(overrides)
    tag = Tag(**defaults)  # type: ignore[arg-type]
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def create_random_article(db: Session, **overrides: object) -> Article:
    # every article needs a publisher; make one unless the caller supplied it
    if "publisher_id" not in overrides:
        overrides["publisher_id"] = create_random_publisher(db).id

    defaults: dict[str, object] = {
        "title": random_lower_string(),
        "url": f"https://example.com/{random_lower_string()}",
        "score": random.randint(1, 10),
        "summary": random_lower_string(),
        "categories": ["dev"],
        "kind": ArticleKind.blog,
        "content": random_lower_string(),
    }
    defaults.update(overrides)
    article = Article(**defaults)  # type: ignore[arg-type]
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def tag_article(db: Session, article: Article, tag: Tag) -> None:
    assert article.id is not None and tag.id is not None
    db.add(ArticleTag(article_id=article.id, tag_id=tag.id))
    db.commit()
