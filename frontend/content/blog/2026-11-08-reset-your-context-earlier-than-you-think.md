---
title: "Reset your context earlier than you think"
description: "Long agent sessions pile up errors. What NVIDIA found when agents restart from a short recap, and two habits to try this week."
topic: context-engineering
---
2026 was the year context windows grew to a million tokens. 2027 is when we ask whether filling them works.

Drew Breunig has an early answer in [The state of context engineering](https://www.dbreunig.com/2026/10/24/the-state-of-context-engineering.html):

> "Long contexts let you fit in more information, but they also let you fit in more errors."

And NVIDIA researchers capped agents at under 50K tokens, made them restart from a short recap, and [accuracy barely moved](https://arxiv.org/abs/2611.05306). They also point out that later tokens cost more:

> "The longer the input context provided to the language model, the slower, more memory hungry, and more expensive its output token generation."

So the useful question is not how much context fits, but how to scope it so errors don't pile up and you don't pay for tokens that don't help. The answer here: restart early, and hand the new session a good brief.

## What goes wrong in a long session

Breunig names five ways a long context fails. Two of them are easy to spot in a coding session.

Inertia: the agent fixes on a hypothesis or subtask and keeps pursuing it after it should stop.

```text
Example session
  turn 5    agent: "the bug is in the cache layer"
  turn 20   test output: cache layer is fine
  turn 35   agent is still editing the cache layer
```

Poisoning: one wrong fact gets into the context and keeps being reused. Breunig's example:

```text
Gemini 2.5 Pro playing Pokemon
  early     a goal from a different game version gets into the context
  then      many hours spent chasing it
```

The other three are distraction, confusion and clash, from his June 2025 post.

Longer contexts leave more room for both. So what happens if you cut the context short on purpose?

## What the paper tested

The paper is "You don't need long context" (Belcak et al., NVIDIA, arXiv 2611.05306). The agent works until its context reaches a low threshold, 12K to 36K tokens, a few percent of a 1M window. Then it starts over:

```text
1. Work on the task.
2. Hit the compaction threshold (12K to 36K tokens).
3. Write a recap.
4. Restart with the original system prompt + the original task + the recap.
```

Files on disk stay between restarts. Only the conversation is thrown away.

Accuracy moved a few points either way with a much smaller context, across all long-horizon (many-step) benchmarks:

| Model | Accuracy change vs no compaction |
|-------|----------------------------------|
| Opus 4.5 | -3.7 to +5.6 points |
| GPT 5.6 Sol | -3.3 to +4.4 points |

Running a model gets more expensive per token as the context grows:

```text
Cost per generated token at 256K, compared with 16K
(open models on H100s, 16K = 1x)

16K                ██              1x
GLM 5.2            ███████         3.6x
Kimi K2.6          ███████████     5.6x
Qwen 3 Coder Next  ██████████████  7x
```

API prices are flat per token, so API users do not see that difference. At today's prices the result is mixed:

```text
Cost of the SWE-bench Verified runs at retail prices
(each █ = $10, ░ = range across thresholds)

Opus 4.5     no compaction  ██████████████████████████████████████████  $420
             compaction     ██████████████████████████████░░░░░░░░      $296 to $380
GPT 5.6 Sol  no compaction  █████████████████                           $168
             compaction     ██████████████████░░                        $184 to $203
```

Opus got about 10% to 30% cheaper and GPT about 10% to 20% more expensive. Accuracy held either way, so the reason to reset is the failure modes above, not money.

Two things make the paper's setup harder in a real coding agent:

- Popular harnesses spend about 32K tokens on the system prompt before you type anything. Tools, MCP servers and CLAUDE.md files are often to blame. A 16K limit does not even fit that.
- Each restart loses the prompt cache, so the new session pays full price for the prompt again.

So copying the paper's loop as-is is not the point. The two ideas worth taking are when to reset and what to hand over.

## Habits to try this week

### Reset at a task boundary, not at the limit

Start a fresh session when one piece of work is done, instead of when the window is full.

The paper compacted at 12K to 36K. Breunig is wary of contexts around 200K to 300K and asks: "Have you tried resetting your context?" It depends on the task.

A plan file makes the boundaries obvious. Write the plan once, then run one session per task:

```text
Example: plans/iso-weeks.md
  1. Parse ISO week dates in parse_date      <- session 1
  2. Handle week 53 and year rollover        <- session 2
  3. Update the docs and changelog           <- session 3
```

Each session starts from the plan file and the task number, not from the last session's chat.

### Hand off with a brief, not a summary

When you reset, give the new session a brief for the work still to do.

The paper restarts with the original system prompt, the original task and a recap. This is the prompt it uses to ask for the recap, from its appendix (template slots removed):

```text
Stop work. Write only a concise handoff recap; do not run commands or call tools.
The conversation will reset to the system prompt, task, and this recap.

Record:
1. Objective - one line describing the required result.
2. Established facts - exact paths, relevant symbols or commands, observed values,
   and important errors/output. Separate observations from unverified ideas.
3. Applied changes - each changed/created file, what changed, and whether verified.
4. Verification - exact checks run, outcomes, failures, obstacles, and workarounds.
5. Dead ends - failed approaches that should not be repeated.
6. Remaining plan - outstanding subgoals, in execution order; the immediate next
   command or edit; and the condition for completion.

If needed output was truncated, give a narrow command to retrieve it.
```

In Appendix A the authors report that the best recaps were briefs for the work still to do, not narratives of what happened. They report it without numbers.

Matt Pocock's [handoff skill](https://github.com/mattpocock/skills/blob/main/skills/productivity/handoff/SKILL.md) does the manual version. It writes a document a fresh agent can continue from, and points to specs, plans, ADRs, issues, commits and diffs by path or URL instead of copying them.

It does not ask for the task verbatim, a step-by-step plan or done conditions. To get closer to the paper's prompt, I would make the skill ask for:

```text
- The original task, copied verbatim.
- Established facts, with observations kept apart from guesses.
- Dead ends: approaches that failed and should not be repeated.
- Remaining plan in order, the next command or edit, and when the task is done.
```

## Limits

- A recap leaves things out.
- The paper tests unattended agent loops, not a person working with an agent all day.
- I have not compared any of this with the built-in compaction in Claude Code or opencode.
- The authors say their evidence does not rule out tasks where long context helps.
