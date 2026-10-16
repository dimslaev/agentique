---
title: "Four unslop skills, one code comment"
description: "I ran four skills that strip AI tells from prose on the same comment, three times each. The skills mostly agree. The runs don't."
topic: agent-skills
---

[Flavio Copes' guide to the unslop skill](https://flaviocopes.com/unslop/) got me curious about the other skills that remove AI tells from prose. I picked four and ran each one three times in headless Claude Code, on the same comment from agentique's pipeline:

```python
# Whatever happened after the fetch, the publishers it polled
# get stamped: on 2026-09-03 a failure after the fetch took the
# per-publisher record with it on exactly the night something
# was wrong. A fetch that itself failed stamps nothing — there
# was no answer to record. Best-effort: bookkeeping never fails
# a source.
```

## The four skills

- [unslop](https://github.com/cursor/plugins/blob/f713f14203cd6420cec13cd7c55c32d598dbab68/pstack/skills/unslop/SKILL.md), from Cursor's pstack, has 28 numbered rules that never get renumbered, so other skills can cite "rule 14". My favorite is rule 27: if a sentence could appear unchanged in another project's docs, cut it.
- [humanizer](https://github.com/blader/humanizer/blob/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8/SKILL.md) ranks its 26 patterns by strength. The top five justify an edit on one sighting, and the weak ones only count when they show up together. It also tells the agent to ask for a missing detail instead of inventing one.
- [stop-slop](https://github.com/hardikpandya/stop-slop/blob/8da1f030185bdfe8471220585162991eaeb970e9/SKILL.md) is the strictest: no adverbs, two items beat three. The agent scores its draft from 1 to 10 on five axes and rewrites it if the total is under 35/50.
- [maxgoff/unslop](https://github.com/maxgoff/unslop/blob/39b3a60c51761ccf434e6677984c2ab9103aa034/skills/unslop/SKILL.md) covers prose, commits, PRs and docs in one file. The rule I'd steal: "Do not document flags, endpoints, or options that do not exist in the code."

## What they changed

Here's the first run of each.

unslop:

```python
# Whatever happened after the fetch, the publishers it polled get stamped.
# On 2026-09-03 a failure after the fetch lost the per-publisher record on
# exactly the night something was wrong. If the fetch itself failed, nothing
# is stamped, because there was no answer to record. Stamping is best-effort
# and never fails a source.
```

humanizer:

```python
# Whatever happened after the fetch, the publishers it polled get stamped.
# On 2026-09-03 a failure after the fetch took the per-publisher record with
# it, on exactly the night something was wrong. If the fetch itself failed,
# nothing is stamped, since there was no answer to record. This is best-effort:
# a bookkeeping error never fails a source.
```

stop-slop:

```python
# Once the fetch returns, every publisher it polled gets stamped, whatever
# fails afterward. On 2026-09-03 a failure after the fetch lost the
# per-publisher record on the night something was actually wrong. If the
# fetch itself fails, nothing gets stamped, because no answer came back.
# The stamping is best-effort and never fails a source.
```

maxgoff/unslop:

```python
# Stamp the polled publishers whatever happens after the fetch. On
# 2026-09-03 a failure after the fetch skipped the per-publisher
# record, on the night something was actually wrong. If the fetch
# itself failed, stamp nothing, since there is no answer to record.
# Best-effort: a bookkeeping error must never fail a source.
```

## What I found

- All 12 runs removed the em dash and the colon after "stamped", and all 12 kept every fact, including the date. On a short technical comment, the four agree more than their rule lists suggest.
- The rest is taste. humanizer kept a colon after "best-effort" in all three runs, which its rules allow and Cursor's rule 14 bans. maxgoff turned the comment into orders every time.
- Three runs of one skill differed about as much as the four skills did. Nothing in a single run tells you which changes come from the skill and which are noise.
- They break their own rules. stop-slop bans adverbs and words like "every", then added "actually" and "every publisher" in its first run. unslop kept the "exactly" in two runs out of three.

## Caveats

- None of them asked whether the comment should exist. Every rewrite is still five or six lines long. They fix wording, not content.
- They don't check meaning. One maxgoff run turned "took the record with it" into "skipped the record", which is a different claim. All three of its runs turned "never fails a source", a description, into "must never fail a source", a rule.
- Your agent may not care either way. [Open Station deleted 168,000 lines of comments](https://openstation.blog/2026/10/13/i-deleted-168000-lines-of-comments-my-ai-agent-didnt-notice/) from a real codebase, and the agent's code was just as good with or without them. Clean comments for the people who read them.

If you try one of these, run it a few times on the same text and compare the results before you trust its rules.
