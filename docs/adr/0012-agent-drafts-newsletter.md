# 12. An agent drafts the weekly newsletter, a person sends it

## Status

Accepted.

## Context

Subscribers have been collected into a Resend audience since the landing page
went up, and nothing was ever sent to them. The feed already holds what an
issue needs: every article was read by the curation agent (ADR 9), scored, and
summarised from the full text, and carries an embedding.

What a list of the week's top scores does not give is the reason to open the
email: the release beside an individual writer who measured it, or a repo that
builds on it. That second article is often not in the same week, and it is
sometimes not in the feed at all, because curation rejects a copy of a story
the feed already carries as a retelling.

## Decision

    Friday 07:52:  week -> pick 3-5 stories -> related for each -> draft_issue
    a person:      reads the preview -> sends it from Resend

- **A Claude Code session writes it.** A second routine on claude.ai/code,
  like curation, runs `.claude/skills/newsletter/SKILL.md` against the MCP
  server with the write token.
- **The tools rank and group; they do not judge.** `week` groups the week's
  articles into stories with curation's embedding maths and ranks them by
  score, then coverage. `related` looks 30 days back at the same subject,
  published articles and rejects that scored 55 or more, and marks each row's
  publisher kind and article kind so the skill can ask for an individual
  writer or a repo directly.
- **The agent writes words, not HTML.** `draft_issue` takes the issue as
  structured fields and the box renders one autoescaped template, so every
  issue looks the same and nothing written can break it.
- **The box holds the key.** The routine runs off-box with only an MCP token;
  `draft_issue` and `send_issue` call Resend from the backend.
- **It drafts; a person sends.** The routine never calls `send_issue`. The
  first issues are read before they go out.
- **Nothing is stored.** An issue covers exactly the 7 days before it, so an
  article cannot be in two, and Resend keeps every broadcast.

## Consequences

The newsletter costs one session a week and no new table. The session's
report names where each link came from, so a bad pick can be traced to the
skill or to the data.

Sending waits on a person every Friday. That is deliberate until a few issues
have gone out as drafted; then the routine can call `send_issue` itself, or
draft with a scheduled send a person can cancel.

`related` embeds the month's rejects on the fly in the API process, as
`similar` does for the week. A few thousand rows a month is fine with
model2vec; an order of magnitude more and the vectors belong on the row.

`publisher_kind` is only as good as the publisher rows: the pipeline creates
unknown publishers as `media`, so the skill reads the URL too. Setting `kind`
on the individual writers the feed already carries makes the newsletter better
without a code change.

Subscriber categories (`dev`, `models`, `research`) are stored on
`newsletter_subscriber` but not on the Resend audience; every subscriber gets
the same issue until the list is big enough to split.
