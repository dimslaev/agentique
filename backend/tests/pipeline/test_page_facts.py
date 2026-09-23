"""Which links an article rests on: repo, model, paper, first-party docs.

The agent reads these instead of fetching the page again to find them, so a
wrong group is a wrong fact about the article. Pinned on fixture HTML, through
the same trafilatura pass the pipeline runs.
"""

from __future__ import annotations

from pipeline.fetching.page_facts import (
    MAX_LINKS_PER_GROUP,
    group_links,
    outbound_links,
)

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
