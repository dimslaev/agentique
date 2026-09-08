# 7. The pipeline reads env at the point of use

## Status

Accepted.

## Context

`pipeline/config.py` opened with "Every environment variable the pipeline reads,
in one place." Every function in it had exactly one caller, in a different
module: `postgres_url()` only in `pipeline/db.py`, `imap_config()` only in
`pipeline/sources/email.py`, `hn_min_points()` only in `pipeline/sources/hn.py`,
and so on for all thirteen. A module whose every member has exactly one caller
elsewhere is not an interface — it is an index, and it costs a second lookup on
every question about how a source is configured.

It also mixed two different kinds of value: deployment secrets (`IMAP_PASSWORD`,
`TAVILY_API_KEY`) and tuning knobs with compiled-in defaults nobody overrides
(`HN_MIN_POINTS`, `DEDUP_DIST_THRESHOLD`). `docs/style.md` already says those two
are different things.

## Decision

`pipeline/config.py` is dissolved. Each env read moves next to its single
consumer: `postgres_url()` into `db.py`, `ImapConfig`/`imap_config()` into
`sources/email.py`, the Tavily key and residential proxy into `sources/http.py`,
`GITHUB_TOKEN` into `sources/github_stars.py`, `AlertConfig`/`alert_config()`
into `health.py`, the traction gate into `sources/hn.py`, the star and dedup
thresholds into `steps/filter.py`, the keep/drop cutoff into `keep_drop.py`.
Names, defaults and laziness are unchanged — no deployment has to do anything.

This is deliberately not what `app/` does. The backend has one validated
pydantic `Settings` object, and that stays: it is a web service whose config is
read on every request and must fail loudly at boot. The pipeline is a batch job
that already reads `os.environ` directly to stay decoupled from that object, and
its config questions are always asked about one source at a time.

The index the module provided is not lost — it moves to `deploy/README.md`,
beside the `/opt/agentique/.env` it actually describes, which is where someone
provisioning a box looks anyway.

## Consequences

"How is the HN traction gate configured" is answered inside
`sources/hn.py`, with the reasoning next to the number. The cost is that no
single Python file lists every var any more, which is why `deploy/README.md`
carries the table and has to be updated when a var is added — a review-enforced
rule, not a compiler-enforced one.
