"""validate_categories: the last line of defence between whatever the LLM
returns and what gets written as ArticleCategory rows.

This carries more weight than the old tag validator did. A category is not a
label on an already-published article — it is the reason the article gets
published at all, so an off-list slug that slipped through would admit an
article nothing actually matched. Nothing is ever minted at runtime; see
pipeline/categories.py.
"""

from __future__ import annotations

from pipeline.categories import normalize_category, validate_categories

VALID = frozenset({"rag", "local-ai", "tool-use-mcp"})


def test_keeps_categories_in_the_vocabulary():
    assert validate_categories(["rag", "local-ai"], VALID) == [
        "rag",
        "local-ai",
    ]


def test_drops_categories_outside_the_vocabulary():
    assert validate_categories(["rag", "robotics"], VALID) == ["rag"]


def test_dedupes_preserving_first_occurrence_order():
    assert validate_categories(["local-ai", "rag", "local-ai"], VALID) == [
        "local-ai",
        "rag",
    ]


def test_caps_at_three_even_if_more_are_valid():
    valid = frozenset({"a", "b", "c", "d"})
    assert len(validate_categories(["a", "b", "c", "d"], valid)) == 3


def test_normalizes_casing_and_underscores_before_validating():
    """The model echoes the display name ("Local AI") or an underscored variant
    at least as often as it copies the slug."""
    assert validate_categories(["Local AI", "RAG"], VALID) == ["local-ai", "rag"]
    assert validate_categories(["local_ai"], VALID) == ["local-ai"]


def test_normalizes_a_display_name_with_an_ampersand():
    """The prompt shows names like "Tool Use & MCP" next to each slug, so the
    model sometimes echoes the name instead of the slug."""
    assert validate_categories(["Tool Use & MCP"], VALID) == ["tool-use-mcp"]


def test_empty_input_yields_no_categories():
    """An article the matcher rejected. This is a normal outcome, and it is what
    stops the article being stored."""
    assert validate_categories([], VALID) == []


def test_all_off_list_yields_no_categories():
    assert validate_categories(["nope", "also-nope"], VALID) == []


def test_normalize_category_rejects_none():
    assert normalize_category(None, VALID) is None


def test_normalize_category_tolerates_an_enum_like_value():
    class _Category:
        value = "rag"

    assert normalize_category(_Category(), VALID) == "rag"
