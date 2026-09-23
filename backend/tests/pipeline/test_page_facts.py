"""Which links an article rests on, and what check_link says about them.

The agent reads the grouped links instead of fetching the page again to find
them, so a wrong group is a wrong fact about the article; they are pinned on
fixture HTML, through the same trafilatura pass the pipeline runs. check_link
is pinned on stubbed API answers: the mapping, and that a failed lookup reads
"unknown" rather than zero.
"""

from __future__ import annotations

import pytest

from pipeline.fetching import page_facts
from pipeline.fetching.page_facts import (
    MAX_LINKS_PER_GROUP,
    UNKNOWN,
    LinkError,
    check_link,
    group_links,
    outbound_links,
)
from pipeline.sources import github_stars

PAGE = "https://blog.example.com/2026/09/release"

# Varied prose on purpose: trafilatura drops a body it reads as boilerplate.
_RELEASE_HTML = """
<html><body>
<nav>
  <a href="/about">About</a>
  <a href="https://github.com/example/website">Star us on GitHub</a>
</nav>
<article>
  <h1>We are releasing Example-7B</h1>
  <p>Today we release Example-7B, a small model trained for tool use. The
  weights are on <a href="https://huggingface.co/example/Example-7B">Hugging
  Face</a> and the training code lives in
  <a href="https://github.com/example/trainer/blob/main/train.py">our trainer
  repo</a>, with the eval harness in
  <a href="https://github.com/example/trainer/tree/main/evals">the same repo</a>.</p>
  <p>The method is described in <a href="https://arxiv.org/abs/2609.01234">the
  paper</a>, and the API reference is at <a href="/docs/api">our docs</a>. We
  also compared against <a href="https://openai.com/index/gpt-6">a frontier
  release</a> on the agentic benchmarks that matter for builders.</p>
  <p>Results on the dataset at
  <a href="https://huggingface.co/datasets/example/tool-evals">tool-evals</a>
  show a clear gain on multi-step calls, while plain chat is roughly flat.
  Community reaction is on <a href="https://x.com/example/status/1">X</a>.</p>
</article>
<footer><a href="https://gitlab.com/example/mirror">Mirror</a></footer>
</body></html>
"""


def test_groups_the_links_an_article_body_makes():
    links = outbound_links(_RELEASE_HTML, PAGE)
    assert links == {
        "model": [
            "https://huggingface.co/example/Example-7B",
            "https://huggingface.co/datasets/example/tool-evals",
        ],
        "repo": ["https://github.com/example/trainer"],
        "paper": ["https://arxiv.org/abs/2609.01234"],
        "docs": [
            "https://blog.example.com/docs/api",
            "https://openai.com/index/gpt-6",
        ],
    }


def test_nav_and_footer_links_are_not_the_articles():
    links = outbound_links(_RELEASE_HTML, PAGE)
    assert "https://github.com/example/website" not in links.get("repo", [])
    assert "https://blog.example.com/about" not in links.get("docs", [])


def test_empty_html_has_no_links():
    assert outbound_links("", PAGE) == {}


def test_every_blob_of_one_repo_is_the_repo():
    urls = [
        "https://github.com/a/b",
        "https://github.com/a/b/pull/12",
        "https://github.com/a/b.git",
        "https://gitlab.com/g/p/-/tree/main",
    ]
    assert group_links(urls, PAGE) == {
        "repo": ["https://github.com/a/b", "https://gitlab.com/g/p"]
    }


def test_papers_come_from_every_paper_host():
    urls = [
        "https://arxiv.org/pdf/2609.01234",
        "https://openreview.net/forum?id=abc",
        "https://doi.org/10.1000/xyz",
        "https://huggingface.co/papers/2609.01234",
    ]
    assert group_links(urls, PAGE) == {"paper": urls}


def test_hugging_face_site_pages_are_not_models():
    urls = [
        "https://huggingface.co/docs/transformers",
        "https://huggingface.co/blog/example",
        "https://huggingface.co/models",
    ]
    # The blog is first-party editorial; the docs and the model index are not
    # anything the article rests on.
    assert group_links(urls, PAGE) == {"docs": ["https://huggingface.co/blog/example"]}


def test_links_to_nowhere_in_particular_are_dropped():
    urls = ["https://x.com/a", "https://news.ycombinator.com/item?id=1", "mailto:a@b"]
    assert group_links(urls, PAGE) == {}


def test_a_link_back_to_the_page_is_not_a_link():
    assert group_links([PAGE, f"{PAGE}#comments"], PAGE) == {}


def test_each_group_is_capped():
    urls = [f"https://arxiv.org/abs/2609.{i:05d}" for i in range(25)]
    assert len(group_links(urls, PAGE)["paper"]) == MAX_LINKS_PER_GROUP


# ─── check_link ──────────────────────────────────────────────────────────────


class _Response:
    def __init__(self, status: int, body: object = None, text: str = "") -> None:
        self.status_code = status
        self._body = body
        self.text = text

    def json(self) -> object:
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _stub_http(monkeypatch, answers: dict[str, _Response]) -> list[str]:
    """Answer each API URL from ``answers`` (by prefix); 404 otherwise."""
    asked: list[str] = []

    def fetch(url: str, **_options: object):
        asked.append(url)
        for prefix, response in answers.items():
            if url.startswith(prefix):
                return response
        return _Response(404)

    monkeypatch.setattr(page_facts, "fetch_with_timeout", fetch)
    monkeypatch.setattr(github_stars, "fetch_with_timeout", fetch)
    return asked


GITHUB_REPO = {
    "description": "Fast inference",
    "stargazers_count": 1234,
    "forks_count": 56,
    "pushed_at": "2026-09-20T10:00:00Z",
    "license": {"spdx_id": "MIT"},
    "archived": False,
}


def test_a_github_repo_maps_to_its_facts(monkeypatch):
    _stub_http(
        monkeypatch,
        {
            "https://api.github.com/repos/a/b/readme": _Response(200, {}),
            "https://api.github.com/repos/a/b": _Response(200, GITHUB_REPO),
        },
    )

    facts = check_link("https://github.com/a/b/tree/main/src")

    assert facts == {
        "url": "https://github.com/a/b",
        "kind": "repo",
        "description": "Fast inference",
        "stars": 1234,
        "forks": 56,
        "last_push": "2026-09-20T10:00:00Z",
        "license": "MIT",
        "archived": False,
        "has_readme": True,
    }


def test_a_repo_with_no_readme_says_so(monkeypatch):
    _stub_http(
        monkeypatch,
        {
            "https://api.github.com/repos/a/b/readme": _Response(404),
            "https://api.github.com/repos/a/b": _Response(200, GITHUB_REPO),
        },
    )
    assert check_link("https://github.com/a/b")["has_readme"] is False


def test_a_rate_limited_github_lookup_is_unknown_not_zero(monkeypatch):
    _stub_http(
        monkeypatch,
        {"https://api.github.com/": _Response(403, text="API rate limit exceeded")},
    )

    facts = check_link("https://github.com/a/b")

    assert facts == {"url": "https://github.com/a/b", "kind": "repo", "lookup": UNKNOWN}


def test_a_missing_field_is_unknown_not_zero(monkeypatch):
    repo = {**GITHUB_REPO, "license": None, "stargazers_count": None}
    _stub_http(
        monkeypatch,
        {
            "https://api.github.com/repos/a/b/readme": _Response(500),
            "https://api.github.com/repos/a/b": _Response(200, repo),
        },
    )

    facts = check_link("https://github.com/a/b")

    assert (facts["license"], facts["stars"], facts["has_readme"]) == (UNKNOWN,) * 3


def test_a_gitlab_project_maps_to_its_facts(monkeypatch):
    asked = _stub_http(
        monkeypatch,
        {
            "https://gitlab.com/api/v4/projects/": _Response(
                200,
                {
                    "description": "Compiler",
                    "star_count": 88,
                    "forks_count": 9,
                    "last_activity_at": "2026-09-01T00:00:00Z",
                    "license": {"key": "apache-2.0"},
                    "archived": True,
                    "readme_url": None,
                },
            )
        },
    )

    facts = check_link("https://gitlab.com/group/sub/proj/-/tree/main")

    assert asked == [
        "https://gitlab.com/api/v4/projects/group%2Fsub%2Fproj?license=true"
    ]
    assert facts == {
        "url": "https://gitlab.com/group/sub/proj",
        "kind": "repo",
        "description": "Compiler",
        "stars": 88,
        "forks": 9,
        "last_push": "2026-09-01T00:00:00Z",
        "license": "apache-2.0",
        "archived": True,
        "has_readme": False,
    }


def test_a_hugging_face_model_maps_to_its_facts(monkeypatch):
    asked = _stub_http(
        monkeypatch,
        {
            "https://huggingface.co/api/models/org/Model-7B": _Response(
                200,
                {
                    "downloads": 5000,
                    "likes": 40,
                    "lastModified": "2026-09-19T00:00:00.000Z",
                    "tags": ["text-generation", "license:apache-2.0"],
                    "siblings": [
                        {"rfilename": "README.md"},
                        {"rfilename": "config.json"},
                        {"rfilename": "model-00001-of-00002.safetensors"},
                    ],
                },
            )
        },
    )

    facts = check_link("https://huggingface.co/org/Model-7B/tree/main")

    assert asked == ["https://huggingface.co/api/models/org/Model-7B"]
    assert facts == {
        "url": "https://huggingface.co/org/Model-7B",
        "kind": "model",
        "downloads": 5000,
        "likes": 40,
        "last_modified": "2026-09-19T00:00:00.000Z",
        "license": "apache-2.0",
        "files": 3,
        "weights": True,
    }


def test_a_model_repo_with_only_a_readme_has_no_weights(monkeypatch):
    _stub_http(
        monkeypatch,
        {
            "https://huggingface.co/api/models/": _Response(
                200,
                {
                    "cardData": {"license": "mit"},
                    "siblings": [{"rfilename": "README.md"}],
                },
            )
        },
    )

    facts = check_link("https://huggingface.co/org/coming-soon")

    assert (facts["weights"], facts["license"], facts["downloads"]) == (
        False,
        "mit",
        UNKNOWN,
    )


def test_a_hugging_face_dataset_has_no_weights_field(monkeypatch):
    _stub_http(
        monkeypatch,
        {
            "https://huggingface.co/api/datasets/org/evals": _Response(
                200, {"downloads": 10, "likes": 1, "siblings": []}
            )
        },
    )

    facts = check_link("https://huggingface.co/datasets/org/evals")

    assert facts["kind"] == "dataset"
    assert facts["files"] == 0
    assert "weights" not in facts


def test_a_failed_hugging_face_lookup_is_unknown(monkeypatch):
    _stub_http(monkeypatch, {})
    facts = check_link("https://huggingface.co/org/Model-7B")
    assert facts["lookup"] == UNKNOWN
    assert "downloads" not in facts


@pytest.mark.parametrize(
    "url",
    [
        "https://arxiv.org/abs/2609.01234",
        "https://openai.com/index/gpt-6",
        "https://github.com/features",
        "https://huggingface.co/spaces/org/demo",
        "https://huggingface.co/blog/release",
    ],
)
def test_anything_else_is_refused_toward_web_fetch(monkeypatch, url):
    asked = _stub_http(monkeypatch, {})
    with pytest.raises(LinkError, match="web_fetch"):
        check_link(url)
    assert asked == []
