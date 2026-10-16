---
title: "Unslop, deslop, no-comments: which one cleans what?"
description: "I ran Cursor's anti-slop skills and antislop-code on agentique's own comments and docs. One rewrote the code to delete every comment."
topic: agent-skills
---

Last month [Flavio Copes wrote up how to use the unslop skill](https://flaviocopes.com/unslop/), and it came through agentique's feed. After that I kept finding more of them: unslop, deslop, anti-slop, no-comments. They all say they remove what a coding agent leaves behind, and I couldn't tell which one cleans what.

I had a reason to care. Coding agents work in agentique's repo every day, and the repo has its own style guide for comments and docs. So I ran a few of these skills on it to see what they would change.

## What a slop skill is

It's a `SKILL.md` file with a checklist that you run as a second pass, after the work is done. [Flavio's reason for the second pass](https://flaviocopes.com/anti-slop/) made sense to me: a last line in the prompt saying "don't sound like AI" competes with everything else the agent is keeping track of. A separate pass has one job.

I found three ways people build them:

- a checklist the agent applies to its own output
- a second agent that reviews output it didn't write
- a linter with no model at all

## Cursor's set

The most interesting set is Cursor's, in [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack). It's split across two plugins, pstack by Lauren Tan and cursor-team-kit, and each skill has one job:

- [`unslop`](https://github.com/cursor/plugins/blob/main/pstack/skills/unslop/SKILL.md) cleans prose. It has 28 numbered rules: AI vocabulary, em dashes, "not X but Y", filler.
- [`deslop`](https://github.com/cursor/plugins/blob/main/cursor-team-kit/skills/deslop/SKILL.md) cleans code. It's about 20 lines long. It reads the diff against main and removes extra comments, try/catch on trusted code paths, `any` casts and deep nesting.
- [`no-comments`](https://github.com/cursor/plugins/blob/main/pstack/skills/no-comments/SKILL.md) handles comments, and it doesn't trust the agent that wrote them.

The pstack guide puts it in one line: "`/deslop` cleans slop out of the code, `/unslop` cleans it out of prose, and `/no-comments` hands the comments to a reviewer who didn't write them." pstack's main skill, `poteto-mode`, runs them at fixed points: unslop on any prose, deslop before each commit, no-comments before review.

Two details in unslop I liked. The rule numbers never change, and a deleted rule leaves a gap, so another skill can say "unslop rule 14" and it always means mid-sentence colons. And rule 27 has a test I now use myself: "if the sentence could appear unchanged in another project's docs, it says nothing about this one. Cut it."

The part I think is really cool is no-comments. It spawns a subagent called [Comment Sicko](https://github.com/cursor/plugins/blob/main/pstack/agents/comment-sicko.md), whose prompt says "I hate comments." The guide explains why it's a separate agent: "An author defends its comments the way you'd defend yours." Comment Sicko's keep list is short: license headers, doc comments on a public API, issue links, and behavior forced by a dependency you can't change. A surprise in your own code doesn't get a comment. It gets a `MUST KILL` flag, which means rename, extract or retype the code until the comment isn't needed. A comment that says "do not remove" gets an offer to turn it into a type, a test or a lint rule.

## Test 1: the comments in run.py

I picked `backend/pipeline/run.py`. It's 123 lines with 8 comments, and most of them are the kind my style guide asks for: "a comment earns its place only for a hidden constraint, a subtle invariant, or a workaround for a specific bug." Here's one:

```python
finally:
    # Whatever happened after the fetch, the publishers it polled
    # get stamped: on 2026-09-03 a failure after the fetch took the
    # per-publisher record with it on exactly the night something
    # was wrong. A fetch that itself failed stamps nothing — there
    # was no answer to record. Best-effort: bookkeeping never fails
    # a source.
```

I ran each skill in headless Claude Code on a clean copy of the repo. I copied the skill files into `.claude/skills/` and the Comment Sicko prompt into `.claude/agents/`.

First, `/no-comments backend/pipeline/run.py`. Comment Sicko's first line was "Yes... Ha ha ha... Yes!", exactly as its prompt says it should be. Then it deleted all 8 comments, including the module docstring and two ADR references, and flagged four places to reshape. The skill did the reshaping too. It moved the error handling into `fail_source` and the bookkeeping into `stamp_publishers`, and it split the big `try` in two, so the `fetched_ok` flag went away:

```python
try:
    fetched, fetch_errors = fetch_source(source)
except Exception as e:
    fail_source(session, source, s, e)
    continue
s.fetched = len(fetched)
```

The rule "a fetch that failed stamps nothing" now lives in the code, not in a comment. I read it twice and I think it behaves the same, but nothing tests `run_pipeline`, so I can't prove it.

One deletion was right in a way I didn't expect. The comment explaining why error messages get truncated repeated what the docstring on `short_error` already says.

Then I ran ruff:

```
D100 Missing docstring in public module
--> pipeline/run.py:1:1
```

My lint config requires a docstring on every module, and Comment Sicko had deleted that one. The skill never ran ruff itself, because the headless session didn't allow it to. The linter caught what the reviewer deleted.

Next I ran [antislop-code](https://github.com/miqdadbadjuber/anti-slop/blob/main/skills/antislop-code/SKILL.md) from miqdadbadjuber/anti-slop on a fresh copy. It's a catalog of comment tells, like banners, "Step 1:" narration and JSDoc that repeats the signature, with a much wider keep list: business logic, security, performance trade-offs, workarounds. It never touches code. It kept 6 of the 8 comments and cut each to one or two lines. The `finally` comment became:

```python
# Stamp polled publishers even when a later step failed; a failed fetch stamps nothing.
# Best-effort: bookkeeping never fails a source.
```

Those read like notes now. unslop's rule 33 calls that over-compression ("dropped articles, verbless fragments"), so these two skills would argue with each other.

Both skills deleted the `# ─── CLI ───` banner and the 2026-09-03 story. Only antislop-code kept the ADR links.

## Test 2: docs/style.md with unslop

`/unslop docs/style.md, the intro and the Backend section` took 20 seconds. Most of the edits were good. "No SQL, no model loading, no branching business rules in a handler body" became "A handler body has no SQL, no model loading, and no business-rule branching." "This is a deliberate, permanent difference" became "The difference is permanent."

But look at the first line it changed:

```diff
- This file is the rest — style a linter cannot express, enforced by review.
+ This file holds the rest: style a linter cannot express, enforced by review.
```

Rule 13 bans the em dash. Rule 14 bans a colon that joins two halves of a sentence. It swapped one for the other. Further down it turned a pair of em dashes into parentheses, which rule 13 also bans by name. Its summary said those parentheses weren't replacing dashes, but they were. Flavio warned about exactly this. Ban one symbol and the habit moves to another.

Its summary of the changes was also a list of bold labels with colons ("**Em dashes and colons:** I replaced..."). That's rule 16. unslop cleaned the file, not its own reply. In Cursor, poteto-mode runs unslop on the agent's replies too, but on its own it doesn't.

## Other repos worth a look

- [scanaislop/aislop](https://github.com/scanaislop/aislop) is a linter with no LLM in it. It has 50+ rules across 10 languages, including Python, scores a change from 0 to 100, and comes with a Claude Code hook. My favorite rule is `meta-comment`, which flags comments about the agent's own process instead of the code.
- [rohitg00/pro-workflow's deslop](https://github.com/rohitg00/pro-workflow/blob/main/skills/deslop/SKILL.md) is Cursor's deslop plus a test run after the edits. It also has a mode that checks a `SKILL.md` for slop: stale lines, dead sentences, the same instruction twice.
- [dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop) is a set of Oxlint rules for TypeScript that you copy into your repo and change, not install. One rule goes the other way and requires a comment: a type assertion needs a written reason. [maharshi365/deslop](https://github.com/maharshi365/deslop) packages those rules for npm.
- [maxgoff/unslop](https://github.com/maxgoff/unslop) covers prose, code, UI and commits in one file. It tells the agent to replace an em dash with a colon or parentheses, the two things Cursor's unslop bans. That made it clear to me that these rules are one person's taste.

For prose-only skills like humanizer and stop-slop, [Flavio's comparison](https://flaviocopes.com/anti-slop/) covers them.

## What I'd do with this

In my test, the most useful check was a lint rule I already had. pstack has a principle for this, [encode lessons in structure](https://github.com/cursor/plugins/blob/main/pstack/skills/principle-encode-lessons-in-structure/SKILL.md): "Encode the rule as a lint, metadata flag, runtime check, or script instead of more text." A skill finds slop. A check stops the next agent from bringing it back, and stops the cleanup skill from going too far.

So run a comment pass before review, read the diff yourself, then run your linter. When the same finding shows up twice, make it a rule. To try Cursor's two in Claude Code or Codex:

```
npx skills add https://github.com/cursor/plugins --skill unslop
npx skills add https://github.com/cursor/plugins --skill deslop
```

For no-comments, also copy `pstack/agents/comment-sicko.md` into `.claude/agents/`, or Claude Code won't find Comment Sicko.

What I still don't know is where the 2026-09-03 story should live. Both skills deleted it, and I agree it doesn't belong above a `finally`. I'm less sure it belongs nowhere.
