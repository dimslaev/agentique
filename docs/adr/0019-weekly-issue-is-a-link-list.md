# 19. The weekly issue is a list of links

## Status

Accepted. Replaces the three-draft essay format in ADR 12 and ADR 15. The rest
of both still stands.

## Context

ADR 12 has the newsletter agent write three explainers a week, one per topic,
for a person to choose from. Two of the three are never sent. The 2026-11-01
issue was instead a short list of the week's best links, chosen with the owner's
likes first and rewritten until the summaries were short enough to read at a
glance.

## Decision

    Friday:    week + liked articles -> rank -> check builder value
               -> use originals -> mix sources -> group -> summarize
               -> draft_issue(post) -> save post -> one PR
    a person:  sends the draft in Resend, merges the PR

- **One draft a week.** 10-12 links in 3-4 sections, with no essay.
- **Likes come first, then score.** Neither keeps an article with no use to a
  builder.
- **Summaries follow one skill.** `.claude/skills/summary/SKILL.md` sets the
  5-10 word rule.
- **The title stays the same, so the date goes in the slug.** The file is
  `<date>-most-interesting-stuff-this-week-<date>.md`. The first date is the
  post date, and the second keeps the URL unique.
- **`sources: false` hides the Sources section.** Every link in the post is
  already a source.

## Consequences

- `draft_issue` still returns a path built from the title, which the skill
  ignores, and refuses the `sources` key. The agent adds that key after drafting.
- The 150-word minimum in `broadcast.py` now applies to a list. Ten links with
  short summaries can fall under it.
- An issue no longer earns traffic as an explainer page. Essays are written by
  hand when a topic deserves one.
