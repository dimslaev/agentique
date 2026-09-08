# 8. One type per pipeline stage

## Status

Accepted.

## Context

Every article moving through the pipeline was a single `FetchedArticle`: one
`TypedDict(total=False)` where all eleven keys were optional at all times. Its
own docstring admitted what that cost — "this documents and typo-checks step
signatures, it does not enforce stage ordering (a step reading a
not-yet-populated key is still a runtime KeyError, same as before)".

So every step had the same signature, `list[FetchedArticle] ->
list[FetchedArticle]`, and none of them said where in the funnel it belonged.
The real contract lived in comments and in the order `run.py` happened to call
things. Reading `steps/score.py` did not tell you that `trust` was already
stamped; reading `steps/enrich.py` did not tell you the rows were already
inserted. You had to read `run.py` to find out, which is the opposite of what
deep modules are for.

The shape also pushed defensive reads everywhere: `a.get("content") or ""`,
`a.get("trust")`, `a.get("topic_gated")`. Each one silently invents a default
for a value that is in fact always present by that point, so a genuinely
missing key produced a wrong answer instead of an error.

## Decision

Four types, one per stage, each fully populated by the step that produces it:

    RawItem    what a source emits
    Candidate  + publisher_id, trust, topic_gated   (fetch.resolve_publishers)
    Scored     + score                              (score.score_articles)
    Persisted  + id                                 (persist.insert_articles)

Each subclasses the one before. A step needing only a `Candidate` still accepts
a `Scored` or a `Persisted`, so the chain composes downward; a step needing a
`score` cannot be handed something that has not been scored, so it does not
compose upward. The signatures are the funnel.

`resolve_publishers` changes from stamping items in place and returning `None`
to returning `list[Candidate]`. It is the only producer of a `Candidate`, which
is what lets everything below it read those three keys with no default.

`ProcessedArticle` is unchanged: it was already narrow and fully populated, and
it is a projection for the embedder rather than another stage.

## Consequences

The defensive `.get` calls are gone, on the keys the stage guarantees. That
turns a class of silent wrong answers into loud failures, and it removes one
behaviour that had a test: an item reaching `drop_off_topic` without
`topic_gated` used to be treated as ungated. It can no longer happen, so the
test now pins the guarantee where it moved to — that `resolve_publishers`
stamps every item it returns.

Runtime `__required_keys__` does not see `NotRequired` under
`from __future__ import annotations`, which the repo requires everywhere. Only
`traction` is affected and nothing introspects these types at runtime; type
checkers read the source and get it right.

Adding a key to a stage now means naming which stage owns it. That is the
point, and it is the only ongoing cost.
