---
title: Is your coding agent breaking its own prompt cache?
description: "Neuralwatt replayed four open-source agents and found what makes them recompute the whole prompt: a date, a reminder, a tool list."
topic: agent-prompt-cache
---
Long agent sessions send 100k tokens or more every turn and get a few hundred back. If the server had to read all of that again each time, nobody could afford it. It doesn't, because of the prompt cache: if this turn's prompt starts with exactly the text of the last one, the server reuses its saved work and only processes the new end.

"Exactly" is the catch. Change one token near the start and everything after it is recomputed. [Neuralwatt](https://neuralwatt.com/news/why-harnesses-matter-for-energy-efficiency), a cloud that bills on measured energy, ran OpenCode, Pi, omp and Kilo Code through a recording proxy. Of 539 follow-up requests, 88% were pure appends. Every one of the other 65 broke because the harness edited something it had already sent.

The causes are specific and small:

- OpenCode 1.x adds a plan-mode reminder to a message, then removes it next turn.
- omp replaces an old file read with "[Superseded by a newer read of this file]". Setting `compaction.supersedeReads: false` stops it.
- The reasoning effort sits at token 8, so changing it re-reads everything.
- MCP tools inserted alphabetically into the middle of the tool list.
- A date in the system prompt.

Why care? They measured that a mostly uncached request used roughly twice the energy of a cached one. Past 128k tokens, one turn that re-reads half its prompt costs about as much prefill as 600 normal turns. These are lab numbers from one company, on two models.

This isn't a new idea. [A writeup on harness design](https://yage.ai/share/prompt-caching-harness-constraint-en-20260404.html) argued earlier that caching reshapes harness design, citing a change to delete the newest tool results first when compacting, so the cache prefix survives. [Antão Almada](https://antaoalmada.dev/posts/Prompt-Caching-for-Coding-Agents) makes the point from the user side: restarting a conversation or switching providers mid-workflow throws the cache away. Neuralwatt's contribution is the per-harness breakdown. Their favorable example is deepseek-harness, which builds every request from an append-only log and puts changed settings after the history.

What would I do with this? If you write a harness, keep the system prompt and tool list fixed and append everything else. If you only use one, pick your reasoning effort and MCP servers before the session gets long. I don't know whether cache hit rates in your own sessions look like theirs. If your tool shows one, look at it.
