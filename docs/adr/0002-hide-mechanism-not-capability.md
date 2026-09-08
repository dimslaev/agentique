# 2. Hide mechanism, never hide capability

## Status

Accepted.

## Context

`routes/articles.py` loaded the model2vec model and defined `_embed` inline
— a route detail hiding the fact that search is semantic at all. That is
buying depth (Ousterhout's "deep module": narrow interface, real
implementation behind it) at the cost of legibility: a reader scanning the
tree cannot tell semantic search exists as a capability.

## Decision

Split by capability, not into one shared bag. `catalog/semantic_search.py`
exposes `search(session, q, limit)` and hides model2vec, the pgvector
distance operator, and snippet capping behind it — the mechanism is hidden,
but the filename still says "this is search." `catalog/facets.py` is a
separate capability (publisher/tag facet counting) with its own file and
its own endpoint, because deleting it doesn't change the search interface —
that's the test for whether two things are one seam or two.

The rule: a module's *name* always screams what it does (its capability).
Only its *body* is allowed to hide how it does it (its mechanism). A module
that hid the fact that search is semantic — folding it into a generically
named `search.py` that could mean anything, or worse, leaving it invisible
inside a route handler — would be trading legibility for depth, which is
the wrong side of that trade here.

## Consequences

Every deep module still passes the screaming-architecture test at the
filename level. Splitting `semantic_search.py` from `facets.py` costs one
extra file for a real benefit: each can change, or disappear, without
touching the other's interface.
