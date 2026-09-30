# 12. An agent drafts three weekly newsletters, a person sends one

## Status

Accepted.

## Context

Subscribers have been collected into a Resend audience since the landing page
went up, and nothing was ever sent to them. The feed already holds the week:
every article was read by the curation agent (ADR 9), scored, summarised from
the full text, and embedded.

A list of the week's top scores is not what a subscriber would open. What is
worth an email is one thing explained well: what it is, how it works, and what
the people who tried it found. That last part is rarely in the article the
feed published. It is in an individual writer's post two weeks later, in the
repo someone built on it, in a Hacker News thread, and sometimes in a copy
curation rejected as a retelling.

"Most talked-about" is also not something the feed can say on its own:
curation approves one copy of a story and rejects the rest, so every story
looks like it was carried once.

## Decision

    Friday 07:52:  week -> 3 topics -> for each: read, search, write -> draft_issue
    a person:      reads the three previews -> sends one from Resend

- **A Claude Code session writes it.** A second routine on claude.ai/code,
  like curation, runs `.claude/skills/newsletter/SKILL.md` against the MCP
  server with the write token.
- **Popularity counts the ledger.** `week` groups the week's articles into
  topics with curation's embedding maths, attaches the ledger rows on the same
  story, and ranks by distinct publishers across both, then likes.
- **The agent reads before it writes.** `related` reaches a month back, rejects
  scored 35 or more included, and marks each row's publisher kind and article
  kind; the agent fetches the first-party source, the individual writers and
  repos, and searches for how people are taking it.
- **One explainer per draft, in a person's voice.** 250-450 words in the tone
  of Julia Evans's posts, linking at least three sources it read. It never
  claims to have run anything itself.
- **Three drafts, one send.** The agent drafts the top three topics; a person
  picks one. The routine never calls `send_issue`.
- **The agent writes prose, not HTML.** `draft_issue` takes plain text with
  paragraphs, list lines, `[text](url)` links and code spans; the box escapes
  the rest and renders one template: the site's wordmark, the prose, links to
  the feed and to unsubscribe.
- **The box holds the key.** The routine runs off-box with only an MCP token;
  `draft_issue` and `send_issue` call Resend from the backend.
- **Nothing is stored.** An issue covers the 7 days before it, and Resend keeps
  every broadcast.

## Consequences

The newsletter costs one session a week and no new table. The session reads
more than curation does per item (up to 4 searches and 8 fetches a topic),
which is affordable once a week and would not be every night.

Sending waits on a person every Friday, by design: they choose the topic as
much as they approve the writing. Two unsent drafts a week pile up in Resend;
deleting them there is the cleanup.

The voice is the risk. A model imitating a writer's tone drifts toward the
tics it was told to avoid, and a first person that "tried" things it never ran
would be making things up. The skill forbids both; the person reading three
previews a week is the check.

`week` and `related` embed the ledger on the fly in the API process, as
`similar` does. A week is under a thousand rows and a month a few thousand,
fine with model2vec; an order of magnitude more and the vectors belong on the
row.

`publisher_kind` is only as good as the publisher rows: the pipeline creates
unknown publishers as `media`, so the skill reads the URL too. Setting `kind`
on the individual writers the feed already carries improves the drafts without
a code change.
