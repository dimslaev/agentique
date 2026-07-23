"""Deterministic pipeline rules that need no LLM or DB."""

from __future__ import annotations

import pytest

from app.models import ArticleKind
from pipeline_new.pipeline import kind_from_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/foo/bar", ArticleKind.repo),
        ("https://gitlab.com/foo/bar", ArticleKind.repo),
        ("https://huggingface.co/meta/model", ArticleKind.model),
        ("https://hf.co/meta/model", ArticleKind.model),
        ("https://arxiv.org/abs/2401.00001", ArticleKind.paper),
        ("https://openai.com/blog/post", None),
        ("https://www.therundown.ai/p/x", None),
    ],
)
def test_kind_from_url(url: str, expected: ArticleKind | None) -> None:
    assert kind_from_url(url) == expected
