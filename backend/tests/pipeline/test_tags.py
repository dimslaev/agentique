"""validate_tags: the last line of defence between whatever the LLM returns and
what gets written as ArticleTag rows. Off-list tags must never be written, and
no tag is ever minted at runtime — see pipeline/tags.py.
"""

from __future__ import annotations

from pipeline.tags import normalize_tag, validate_tags

VALID = frozenset({"llm", "agents", "open-source"})


def test_keeps_tags_in_the_vocabulary():
    assert validate_tags(["llm", "agents"], VALID) == ["llm", "agents"]


def test_drops_tags_outside_the_vocabulary():
    assert validate_tags(["llm", "not-a-real-tag"], VALID) == ["llm"]


def test_dedupes_preserving_first_occurrence_order():
    assert validate_tags(["agents", "llm", "agents"], VALID) == ["agents", "llm"]


def test_caps_at_three_even_if_more_are_valid():
    valid = frozenset({"a", "b", "c", "d"})
    assert len(validate_tags(["a", "b", "c", "d"], valid)) == 3


def test_normalizes_casing_and_underscores_before_validating():
    assert validate_tags(["LLM", "open_source"], VALID) == ["llm", "open-source"]


def test_empty_input_yields_no_tags():
    assert validate_tags([], VALID) == []


def test_all_off_list_yields_no_tags():
    assert validate_tags(["nope", "also-nope"], VALID) == []


def test_normalize_tag_rejects_none():
    assert normalize_tag(None, VALID) is None


def test_normalize_tag_tolerates_an_enum_like_value():
    class _Tag:
        value = "llm"

    assert normalize_tag(_Tag(), VALID) == "llm"
