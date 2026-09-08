# 3. No module named utils

## Status

Accepted.

## Context

The repo had five: `app/utils.py` (email), `pipeline/utils.py` (nine
unrelated helpers), `api/routes/utils.py` (not utils at all — a route
module), `frontend/src/utils.ts` (error handling + initials),
`frontend/src/lib/utils.ts` (shadcn's `cn()`). A `utils/` folder with one
file per helper does not fix this — it spreads the grab bag over more
inodes while the folder name still says nothing. It fails the screaming
test at the exact level the test is about.

## Decision

No module anywhere in the repo is named `utils`, `helpers`, `common`,
`shared`, or `misc`. Name a helper by what it holds and put it where it is
used: `log`/`wait_ms`/`short_error` → `app/platform/logging.py`;
`feed_url`/`hostname` → `pipeline/urls.py`; `is_within_window` →
`pipeline/freshness.py` (it encodes the freshness rule, a domain decision,
not a date helper); `clean_title` → `pipeline/titles.py`; and so on. If a
good name is hard to find, the function does not have a job yet — leave it
beside its only caller until a second caller proves the seam.

One documented exception: `frontend/src/lib/utils.ts` holding `cn()` stays,
because it is shadcn convention and every generated component imports it by
that exact path — renaming it fights the code generator forever. That is
the only grandfathered `utils` file in the repo, and it stays that way on
purpose rather than by oversight.

## Consequences

Enforced by a local pre-commit hook that greps the tracked file list and
fails on a banned name (see `docs/style.md`), so this cannot silently
regress. A reviewer who sees a new `utils.py` in a diff has grounds to
reject it on sight, no discussion needed.
