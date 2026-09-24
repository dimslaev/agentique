"""The pipeline's steps, in the order run.py applies them.

    fetch     - poll each source, fill content, stamp each item's publisher
    filter    - drop URLs already judged or already waiting
    queue     - park each survivor as a pending candidate. The last step.

The curation agent takes it from there (pipeline/curation.py): approving a
candidate runs persist and enrich (the embedding) on that one article, with
the summary, categories, kind and tags the agent wrote -- see
docs/adr/0009-agent-curation.md.

Every step takes the session and a list of articles and returns the survivors,
so run.py reads as the funnel it is. Steps own their own logging and commits.

The article changes type as it goes -- RawItem -> Candidate -> Scored ->
Summarized -> Persisted, see pipeline.types -- so a step's signature says where
in the funnel it belongs.
"""

from __future__ import annotations

# How much of an article goes into its embedding. The title carries most of
# the signal; the opening sentence or two sharpens it.
SNIPPET_CAP = 200
