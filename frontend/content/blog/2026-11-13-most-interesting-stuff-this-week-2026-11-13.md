---
title: The most interesting stuff this week
description: Small decision models replacing big ones, skills that make coding agents audit and review, and short contexts that cost no accuracy.
topic: most-interesting-this-week
sources: false
---
Decision models

- [Amazon saves millions by replacing Sonnet 4.6 with Strands Decider](https://strandsagents.com/blog/amazon-saves-millions-replacing-sonnet-with-strands-decider/). A 4B decision model cut ticket labeling costs 98%.
- [A Jev that can ask Opus for help gives Opus accuracy at 4x lower cost](https://hightouch.com/blog/llm-judges-identity-resolution). Escalation only works if the cheap judge is calibrated.

Coding agent skills

- [Get your coding agent off ~2019 JavaScript, onto modern web primitives](https://github.com/GoogleChrome/modern-web-guidance). Browser vendors wrote 200 guides on native features for agents.
- [security-audit-skill](https://github.com/cloudflare/security-audit-skill). The agent that checks a finding never found it.
- [Elephant-Goldfish](https://github.com/google/elephant-goldfish-model). Subagents with no context review specs before coding starts.
- [Stroq](https://github.com/AGGIB/Stroq). It shows which of your keys agent sessions sent out.

Agent runs

- [You don't need long context](https://arxiv.org/abs/2611.05306). Frequent compaction costs frontier models almost no accuracy.
- [Batch, Then Aggregate: Better Agentic Coding with Parallel Attempts](https://kaitchup.substack.com/p/batch-then-aggregate-better-agentic). Merging four attempts solved 61% of tasks, one solved 47%.

Models

- [Claude Fable 5.2 and Mythos 5.2](https://www.anthropic.com/claude-fable-and-mythos-5-2). At high effort it matches Opus 5.5 for half the cost.
- [Introducing Gemini 4 Hydrogen](https://deepmind.google/blog/introducing-gemini-4-hydrogen/). The cheapest Gemini 4 model scores above Gemini 4 Argon.
- [Muse Ember: Our smallest, most efficient model](https://research.meta.ai/blog/muse-ember). It scores near Muse Spark for $0.14 a task, not $2.39.
- [Introducing Arete-27B: Qwen3.8-27B Post-Trained To Reinforce Western Values](https://nousresearch.com/arete). One small fine-tune removed nearly all of Qwen's propaganda answers.
