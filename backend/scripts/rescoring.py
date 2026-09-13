"""What the two rescore scripts share: which model judges, and when a run gives up.

Both call the pipeline's own ScoreArticles prompt, so a rescore is judged by the
same rubric as a nightly run; only the model and the text it is shown differ.
"""

from __future__ import annotations

from baml_client.sync_client import b
from baml_client.types import ArticleInput, ScoredArticle

# --model value -> client name in baml_src/clients.baml. Deliberately no
# fallback chain: a rescore judged half by one model and half by another is not
# one rescore, so an outage stops the run instead of switching judges.
MODELS = {"nemotron": "Nemotron", "gpt-oss-20b": "GptOss20b"}
DEFAULT_MODEL = "nemotron"

# BAML's retry policy has already retried each call. Several batches failing in
# a row after that is the provider being down, not a bad batch: stop and let the
# next run resume, rather than walk every remaining row into a failure.
MAX_FAILED_BATCHES_IN_A_ROW = 3


def score_batch(inputs: list[ArticleInput], model: str) -> dict[str, ScoredArticle]:
    """The scorer's verdicts keyed by URL. An input it did not answer for is
    absent - never read that as a low score. Raises if the call itself failed."""
    results = b.ScoreArticles(inputs, baml_options={"client": MODELS[model]})
    return {r.url: r for r in results}
