# 15. Each weekly issue is also a blog post

## Status

Accepted.

## Context

ADR 12 has the newsletter agent draft three issues a week in Resend and store
nothing: Resend keeps the broadcasts. The blog was separate: posts written by
another skill, with their own frontmatter (`slug`, `date`, `articles`) and
their own content rules checked by the blog build. Two skills, two formats and
two rulebooks for what is the same thing, a short explainer with its sources.

An issue is worth more than one inbox visit. The three drafts a week are each
an indexable page, and only one of them is ever sent.

## Decision

    Friday:    week -> 3 topics -> for each: read, write -> draft_issue(post) -> save post
               -> one PR with the three posts
    a person:  sends one draft in Resend, merges the PR

- **One skill.** `.claude/skills/newsletter/SKILL.md` is the only description
  of the weekly job, and the routine's prompt only names it.
- **One file format for email and blog.** An issue is
  `frontend/content/blog/<YYYY-MM-DD>-<slug>.md`: frontmatter with `title`
  (the subject), `description` (the preheader) and `topic` (names the draft),
  then the body in the issue's plain-text format. Date and slug come from the
  filename only.
- **`draft_issue` owns the content rules.** It takes the whole file, refuses
  one that breaks a rule (lengths, word count, at least three sources), drafts
  the broadcast and returns the path to save the file at. The blog build checks
  only what a page needs to render.
- **The PR is the blog's review step.** The routine commits the three posts on
  a branch and opens one PR; merging publishes them.
- **Git stores the issues.** The posts are the record; Resend still keeps the
  broadcasts.

## Consequences

The agent passes the same text to `draft_issue` and to the file, so the email
and the page cannot drift. A rule change happens in one place,
`app/newsletter/broadcast.py`.

The routine now writes to the repo: it needs push access and leaves a PR every
week. An unmerged PR means the posts are not on the blog; the email does not
wait on it.

Two of the three posts each week were never sent as email. They are still
reviewed in the PR, and a person can drop one there before merging.

The frontmatter is parsed twice, by `broadcast.py` and by the blog build's YAML
parser. `broadcast.py` refuses an unquoted value YAML would misread, so a post
it accepts is one the build can read.
