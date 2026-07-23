"""RSS/substack ingestion pipeline (rewrite).

Self-contained: nothing here imports ``pipeline.*``. It reuses only the
generated ``baml_client`` and the schema in ``app.models``. Scope is RSS and
substack feeds only — the two publisher kinds that survive the rewrite. Every
feed already carries the article body (``content:encoded``), so the network is
touched again only for the rare thin entry, and only through a residential
proxy fallback. Every value that reaches the DB is sanitized first.

The flow is one object, ``PipelineArticle``, carried through the stages in
``pipeline_new.pipeline``:

    fetch    -> url, title, content, publisher (id/name/trust)
    filter   -> drop known URLs and semantic duplicates
    score    -> keep/drop pre-filter, then the LLM scorer
    persist  -> insert what cleared the bar
    enrich   -> full content (only if thin), summary/categories/kind, tags, embed
"""
