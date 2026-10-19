"""The label vocabulary and the join that puts labels on articles."""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True)
    name: str
    # "when to apply this tag" — fed to the AssignTags prompt as the vocabulary
    description: str | None = None


class ArticleTag(SQLModel, table=True):
    __tablename__ = "article_tag"
    article_id: int = Field(foreign_key="article.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)
