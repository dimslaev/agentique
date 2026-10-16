---
title: "Four unslop skills, one code comment"
description: "I asked four anti-slop skills to tighten one code comment, 36 times. The best run cut 51 words to 37, and none dropped the part I would."
topic: agent-skills
---

[Flavio Copes' guide to the unslop skill](https://flaviocopes.com/unslop/) got me curious about the other skills that remove AI tells from prose. I picked four and gave them one comment from agentique's pipeline, in headless Claude Code:

```python
# Whatever happened after the fetch, the publishers it polled
# get stamped: on 2026-09-03 a failure after the fetch took the
# per-publisher record with it on exactly the night something
# was wrong. A fetch that itself failed stamps nothing — there
# was no answer to record. Best-effort: bookkeeping never fails
# a source.
```

I tried three ways, three runs each: rewrite the comment alone, tighten it alone (the way Flavio's guide prompts `/unslop`), and tighten it in place in `run.py` with the code around it. The results were disappointing.

## The four skills

- [unslop](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/unslop/SKILL.md), from Cursor's pstack, has 28 numbered rules that never get renumbered, so other skills can cite "rule 14". My favorite is rule 27: if a sentence could appear unchanged in another project's docs, cut it.
- [humanizer](https://github.com/blader/humanizer/blob/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8/SKILL.md) ranks its 26 patterns by strength. The top five justify an edit on one sighting, and the weak ones only count together.
- [stop-slop](https://github.com/hardikpandya/stop-slop/blob/8da1f030185bdfe8471220585162991eaeb970e9/SKILL.md) is the strictest: no adverbs, two items beat three, and a 1-10 self-score on five axes with a rewrite under 35/50.
- [maxgoff/unslop](https://github.com/maxgoff/unslop/blob/39b3a60c51761ccf434e6677984c2ab9103aa034/skills/unslop/SKILL.md) covers prose, commits, PRs and docs in one file. The rule I'd steal: "Do not document flags, endpoints, or options that do not exist in the code."

## What came back

Word counts across three runs. The original is 51 words.

| Skill | Rewrite | Tighten | Tighten, with code |
|---|---|---|---|
| unslop | 51-54 | 48 | 47-49 |
| humanizer | 52-59 | 44 | 42 |
| stop-slop | 53-54 | 46-49 | 41-44 |
| maxgoff/unslop | 50-51 | 43-45 | 37-43 |

The shortest of all 36, maxgoff/unslop with the code open:

```python
# Stamp polled publishers even if a later step failed: on
# 2026-09-03 such a failure lost the per-publisher record on
# the night it mattered. A failed fetch stamps nothing (no
# answer to record). Best-effort: never fails the source.
```

unslop with the code open:

```python
# Stamp the polled publishers even if a later step failed. On
# 2026-09-03 such a failure lost the per-publisher record on the
# night something was wrong. A failed fetch stamps nothing,
# since there is no answer to record. A bookkeeping error is
# logged and never fails the source.
```

## What I found

- Every result is four to six lines, against six in the original. The em dash goes, and most of the comment stays.
- All 36 runs kept the 2026-09-03 story, the part I'd cut first. Every run that saw the code mentioned it in its summary, usually as a fact it had kept. That's by design. unslop says "Preserve meaning", and humanizer says "Keep every supported claim." These skills remove tells. They don't decide what's worth saying.
- Seeing the code made them more accurate, not shorter. Three runs read the `except` below the comment and added that errors are "logged", which is true and wasn't in the original.
- Tightening brought tells back. With the code open, 6 of 12 runs joined two sentences with a colon, which Cursor's rule 14 bans. maxgoff/unslop swapped the em dash for parentheses twice, which rule 13 bans.
- Three runs of one skill differed about as much as the four skills did.

## Caveats

- They don't check meaning. Asked to rewrite, maxgoff/unslop turned "never fails a source", a description, into "must never fail a source", a rule, in all three runs.
- Your agent may not care either way. [Open Station deleted 168,000 lines of comments](https://openstation.blog/2026/10/13/i-deleted-168000-lines-of-comments-my-ai-agent-didnt-notice/) from a real codebase, and the agent's code was just as good without them. Clean comments for the people who read them.

If you want a shorter comment, say so directly, or use a skill written for comments. These are for text where the AI tells are the problem.
