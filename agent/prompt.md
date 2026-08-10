# Curation run

Work through today's inbox. Read `agent/CLAUDE.md` first — the tool API, the
scoring rubric, the taxonomy and the attribution rules are all there, and this
file assumes them.

## Mode

Default is **live**: you publish. If the human said "dry run", change one thing
— do not call `POST /agent/articles` and do not call
`POST /agent/feed-items/{id}/decision` — and print exactly the same summary,
saying what you *would* have published. Everything else, fetches and searches
included, runs the same way.

## Loop

Repeat until `GET /agent/feed-items?status=new` reports `count: 0`, or until the
human's budget for the run is spent.

**1. Pull a batch.** `GET /agent/feed-items?status=new&limit=10`. Note `count`
so you know how deep the inbox is.

**2. Triage on the title.** Before any fetch, decide which items in the batch
could plausibly clear 65. Most cannot: crypto, funding rounds, lawsuits, hiring,
general programming, chip supply chain, AI-flavoured business commentary. Reject
them now with a one-line reason — no fetch, no search. This is where the volume
dies, and being decisive here is what makes the run affordable.

Be honest about uncertainty: a title you cannot judge is a survivor, not a
reject. "Unfamiliar repo name" is a reason to look, not a reason to drop.

**3. Resolve the source.** For each survivor, work out what the item actually
points at (see Attribution in `agent/CLAUDE.md`). An aggregator item needs this;
a first-party post does not. Do the resolution before fetching, so you fetch the
original rather than the recap.

**4. Fill in the content.** If the feed text is already a real article, use it.
If it is empty or a teaser, `POST /agent/fetch-url` on the resolved URL. If that
comes back `ok: false`, try the next candidate link; if there isn't one, judge
on the title and cap the score at 70 per the rubric.

**5. Score it.** Apply the rubric. Below 65 → reject, with the reason stated in
the rubric's terms ("landing page, no method", "PM-audience explainer, caps at
40"), not just "low quality".

**6. Check it is not already there.** For each survivor still standing:
`GET /api/v1/articles/search?q=<resolved title>&limit=5`. Read the top hits — a
close cosine distance on a generic title is not a duplicate, and the same
release covered by two publishers on the same day is. If it is a duplicate,
reject with "duplicate of #<id>".

**7. Publish.** `POST /agent/articles` with url, title, publisher_slug, score,
kind, categories, summary, content, published_at and up to 3 tags. Create the
publisher first if the first party is new.

**8. Mark it.** `POST /agent/feed-items/{id}/decision` for every item in the
batch — the accepts too. Then take the next batch.

## Budget

Guide numbers for a normal day, not hard limits. A day well outside them is
worth a line in the summary.

| | expected |
|---|---|
| items seen | 50-100 |
| survive title triage | 15-25 |
| `fetch_url` calls | 15-25 |
| `articles/search` calls | ~10 |
| published | 8-12 |

If you are publishing 30, the bar has slipped — reread the bands. If you are
publishing 2, check you are not rejecting first-party releases on thin titles.

## Summary

Print this at the end, and nothing else after it:

```
RUN <date>  [live|dry-run]
seen N · accepted N · rejected N · left in inbox N

PUBLISHED
  92  <title>  [<publisher>]  <url>
  ...

NOTABLE REJECTS
  <title> — <reason>          (only the ones a human might disagree with)

REJECT REASONS
  out of scope         N
  below threshold      N
  duplicate            N
  no content, thin     N

PROBLEMS
  <anything that went wrong: fetch failures, 409s, publishers you had to
   invent, items you were unsure about. "none" if none.>
```

The PROBLEMS section is the point of the summary. Nothing watches this run —
if you do not say something went wrong, nobody finds out.
