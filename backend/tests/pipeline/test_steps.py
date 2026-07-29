"""The pure cores of the categorize / persist / enrich steps.

These carry the decisions that silently change what gets published — what counts
as a match, which article wins a duplicate URL, whether an LLM rewrite is allowed
to replace a title — so they are pulled out of the I/O steps and pinned here.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.models import ArticleKind
from pipeline.steps.categorize import apply_matches, max_similarity
from pipeline.steps.enrich import accept_title
from pipeline.steps.persist import best_per_url, resolve_kind

VALID = frozenset({"rag", "local-ai", "open-weights"})


def _article(url: str, source: str = "Hacker News", **extra) -> dict:
    return {"title": "A title", "url": url, "source": source, **extra}


# ─── apply_matches ───────────────────────────────────────────────────────────


def _match(categories, kind="Blog"):
    """One MatchCategories response entry, as apply_matches consumes it."""
    return (categories, kind)


def test_attaches_each_articles_categories_by_url():
    articles = [_article("u1"), _article("u2")]
    matched = apply_matches(
        articles,
        {"u1": _match(["rag"]), "u2": _match(["local-ai", "open-weights"])},
        VALID,
    )
    assert {m["url"]: m["categories"] for m in matched} == {
        "u1": ["rag"],
        "u2": ["local-ai", "open-weights"],
    }


def test_article_matching_no_category_is_dropped():
    """The whole editorial policy in one assertion: no category, not stored."""
    assert apply_matches([_article("u1")], {"u1": _match([])}, VALID) == []


def test_article_the_matcher_omitted_is_dropped():
    """A missing answer must read as a reject, never as a pass — the matcher
    dropping an item from its response must not let it through unjudged."""
    assert apply_matches([_article("u1")], {}, VALID) == []


def test_off_list_categories_cannot_admit_an_article():
    """If every returned slug is invented, the article has no valid category and
    must not survive on the strength of a hallucination."""
    assert (
        apply_matches(
            [_article("u1")], {"u1": _match(["robotics", "sovereign-ai"])}, VALID
        )
        == []
    )


def test_keeps_an_article_whose_only_valid_category_survives_validation():
    matched = apply_matches(
        [_article("u1")], {"u1": _match(["robotics", "rag"])}, VALID
    )
    assert matched[0]["categories"] == ["rag"]


def test_carries_the_kind_hint_through():
    """Format rides on the same response as the categories, so it costs no
    extra call — but it is only a hint until persist resolves it."""
    matched = apply_matches(
        [_article("u1")], {"u1": _match(["rag"], kind="Paper")}, VALID
    )
    assert matched[0]["kind_hint"] == "Paper"


def test_does_not_mutate_the_articles_it_is_given():
    articles = [_article("u1")]
    apply_matches(articles, {"u1": _match(["rag"])}, VALID)
    assert "categories" not in articles[0]


def test_preserves_the_rest_of_the_article():
    matched = apply_matches(
        [_article("u1", publisher_id=7, content="body")],
        {"u1": _match(["rag"])},
        VALID,
    )
    assert matched[0]["publisher_id"] == 7
    assert matched[0]["content"] == "body"


# ─── max_similarity ──────────────────────────────────────────────────────────


def test_max_similarity_picks_the_closest_prototype():
    prototypes = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    vecs = np.array([[2.0, 0.0], [0.0, 5.0]], dtype=np.float32)
    assert np.allclose(max_similarity(vecs, prototypes), [1.0, 1.0])


def test_max_similarity_is_scale_invariant():
    """Article vectors are normalised inside, so a longer article does not clear
    the gate just by having a bigger vector."""
    prototypes = np.array([[1.0, 0.0]], dtype=np.float32)
    short = max_similarity(np.array([[1.0, 1.0]], dtype=np.float32), prototypes)
    long = max_similarity(np.array([[50.0, 50.0]], dtype=np.float32), prototypes)
    assert np.allclose(short, long)


def test_max_similarity_scores_an_orthogonal_article_at_zero():
    prototypes = np.array([[1.0, 0.0]], dtype=np.float32)
    vecs = np.array([[0.0, 1.0]], dtype=np.float32)
    assert np.allclose(max_similarity(vecs, prototypes), [0.0])


def test_max_similarity_survives_a_zero_vector():
    """A contentless item embeds to zeros; dividing by its norm must not blow up
    the whole batch."""
    prototypes = np.array([[1.0, 0.0]], dtype=np.float32)
    vecs = np.array([[0.0, 0.0]], dtype=np.float32)
    assert np.allclose(max_similarity(vecs, prototypes), [0.0])


def test_max_similarity_on_empty_input():
    prototypes = np.array([[1.0, 0.0]], dtype=np.float32)
    assert len(max_similarity(np.empty((0, 2), dtype=np.float32), prototypes)) == 0


# ─── best_per_url ────────────────────────────────────────────────────────────


def test_same_url_from_two_sources_unions_their_categories():
    """Two sources can surface one URL in a run (an HN post and a feed item for
    the same post). Both judgements were made about the same article, so
    dropping one would lose a lane for no reason."""
    items = [
        _article("dupe", source="Hacker News", categories=["rag"]),
        _article("dupe", source="Feeds", categories=["open-weights"]),
    ]
    best = best_per_url(items)
    assert len(best) == 1
    assert best[0]["categories"] == ["rag", "open-weights"]


def test_union_does_not_duplicate_a_shared_category():
    items = [
        _article("dupe", categories=["rag", "local-ai"]),
        _article("dupe", categories=["local-ai"]),
    ]
    assert best_per_url(items)[0]["categories"] == ["rag", "local-ai"]


def test_union_is_capped_at_three():
    items = [
        _article("dupe", categories=["rag", "local-ai"]),
        _article("dupe", categories=["open-weights", "tool-use-mcp"]),
    ]
    assert len(best_per_url(items)[0]["categories"]) == 3


def test_first_occurrence_wins_on_everything_but_categories():
    """No score to break the tie any more, so the earlier item keeps the row."""
    items = [
        _article("dupe", source="Hacker News", categories=["rag"]),
        _article("dupe", source="Feeds", categories=["local-ai"]),
    ]
    assert best_per_url(items)[0]["source"] == "Hacker News"


def test_distinct_urls_all_survive():
    items = [
        _article("u1", categories=["rag"]),
        _article("u2", categories=["local-ai"]),
    ]
    assert len(best_per_url(items)) == 2


def test_empty_input():
    assert best_per_url([]) == []


def test_does_not_mutate_the_items_it_is_given():
    items = [
        _article("dupe", categories=["rag"]),
        _article("dupe", categories=["local-ai"]),
    ]
    best_per_url(items)
    assert items[0]["categories"] == ["rag"]


# ─── resolve_kind ────────────────────────────────────────────────────────────


def test_url_host_beats_the_models_guess():
    """A github.com link is a repo. No model gets a vote on that."""
    assert resolve_kind("https://github.com/a/b", "", "Blog") == ArticleKind.repo
    assert resolve_kind("https://arxiv.org/abs/1", "", "Product") == ArticleKind.paper
    assert resolve_kind("https://huggingface.co/x", "", "Blog") == ArticleKind.model


def test_falls_back_to_the_hint_when_the_host_says_nothing():
    assert resolve_kind("https://example.com/x", "", "Paper") == ArticleKind.paper


def test_hint_is_case_insensitive():
    assert resolve_kind("https://example.com/x", "", "ANNOUNCEMENT") == (
        ArticleKind.announcement
    )


def test_unknown_hint_falls_back_to_blog_rather_than_raising():
    assert resolve_kind("https://example.com/x", "", "Newsletter") == ArticleKind.blog


def test_missing_hint_falls_back_to_blog():
    assert resolve_kind("https://example.com/x", "", None) == ArticleKind.blog


def test_a_blog_that_links_a_repo_is_a_repo():
    content = "Check out https://github.com/owner/project for the code."
    assert resolve_kind("https://example.com/x", content, "Blog") == ArticleKind.repo


def test_repo_link_does_not_override_a_more_specific_hint():
    """Every paper announcement links its code. That does not make it a repo."""
    content = "Code at https://github.com/owner/project"
    assert resolve_kind("https://example.com/x", content, "Paper") == ArticleKind.paper


# ─── accept_title ────────────────────────────────────────────────────────────

_CURRENT = "The original title"
_SOURCE = "Hacker News"


def test_accepts_a_clean_rewrite():
    assert (
        accept_title("A clear specific technical title", _CURRENT, _SOURCE)
        == "A clear specific technical title"
    )


def test_strips_wrappers_before_accepting():
    assert (
        accept_title('"[HN] A clear specific title"', _CURRENT, _SOURCE)
        == "A clear specific title"
    )


@pytest.mark.parametrize("given", [None, "", "   "])
def test_no_rewrite_offered_keeps_the_original(given):
    assert accept_title(given, _CURRENT, _SOURCE) is None


def test_rewrite_identical_to_the_current_title_is_not_a_change():
    assert accept_title(_CURRENT, _CURRENT, _SOURCE) is None


def test_rejects_a_rewrite_that_leaked_the_source_name():
    assert accept_title("Hacker News covers a new model", _CURRENT, _SOURCE) is None


def test_source_leak_check_is_case_insensitive():
    assert accept_title("hacker news covers a model", _CURRENT, _SOURCE) is None


@pytest.mark.parametrize(
    "given, why",
    [
        ("Two words", "under the 3-word minimum"),
        ("word " * 25, "over the 20-word maximum"),
        ("Read more at https://example.com/x", "contains a URL"),
        ("Title with\na newline", "spans lines"),
        ('{"title": "leaked envelope"}', "leaked the JSON envelope"),
        ("这是一个中文标题", "drifted out of English"),
    ],
)
def test_rejects_malformed_rewrites(given, why):
    assert accept_title(given, _CURRENT, _SOURCE) is None, why
