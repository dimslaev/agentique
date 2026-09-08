"""The extraction gate: distinguishing a real article body from a paywall/login
wall/teaser that happened to return 200. A false negative here means real
content is silently dropped; a false positive means a blocker page gets
summarized as if it were the article.
"""

from __future__ import annotations

import pytest

from pipeline.fetching.extract_content import _is_blocker

_REAL_ARTICLE = (
    "Anthropic shipped a new model today with a longer context window and "
    "noticeably faster tool use, three months after the previous flagship. "
    "Pricing drops to five dollars per million input tokens."
)


def test_a_real_article_body_is_not_a_blocker():
    assert _is_blocker(_REAL_ARTICLE) is False


@pytest.mark.parametrize(
    "given",
    [
        "too short",
        "",
    ],
)
def test_anything_under_50_chars_is_a_blocker(given):
    """A teaser must not masquerade as an article regardless of its wording."""
    assert _is_blocker(given) is True


@pytest.mark.parametrize(
    "given",
    [
        "Please sign in to continue reading this article and many more premium features.",
        "Subscribe to continue reading this exclusive members-only content today.",
        "You need to create an account to access this content on our platform.",
        "Please enable javascript to view this page properly in your browser.",
        "Access denied: you do not have permission to view this resource here.",
        "403 Forbidden: the server refused to fulfill this particular request.",
        "Something went wrong loading this page, but don't fret, try again soon.",
    ],
)
def test_known_blocker_wording_is_flagged(given):
    assert _is_blocker(given) is True


def test_blocker_wording_is_flagged_regardless_of_casing():
    assert (
        _is_blocker("PLEASE SIGN IN TO CONTINUE reading this long article now.") is True
    )


def test_a_long_article_about_auth_is_not_flagged():
    """The patterns target a page THAT IS a wall, not an article about the
    general topic of authentication — wording matters, not the subject."""
    text = (
        "This tutorial walks through building an OAuth flow: after entering "
        "credentials, the browser is redirected back with an authorization "
        "code, which the backend exchanges for a token. The rest of this long "
        "guide covers refresh tokens and how a typical web application handles "
        "session storage, with code samples for both frontend and backend."
    )
    assert _is_blocker(text) is False


def test_wording_close_to_but_not_matching_a_pattern_is_not_flagged():
    """Documents that the gate is substring-driven, not semantic: an article
    that happens to use the exact phrase "sign in to continue" mid-sentence
    would be misflagged even outside a real wall. Regression coverage for that
    known sharp edge if the patterns are ever loosened further."""
    text = (
        "The onboarding flow asks a returning user to confirm their identity "
        "before continuing to the dashboard, which is a much longer sentence "
        "than any real paywall message would ever use in production today."
    )
    assert _is_blocker(text) is False
