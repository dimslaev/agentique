---
title: The most interesting stuff this week
description: Agents reviewing code, swarms forming bureaucracies, and a 1-trillion-parameter open model.
topic: most-interesting-this-week
sources: false
---
Code review

- [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/). Merged PRs more than doubled while the revert share fell by over 40%.
- [AI agent fixed the bug, but what else did it change?](https://blog.trailofbits.com/2026/10/21/your-ai-agent-fixed-the-bug-but-what-else-did-it-change/) Trail of Bits found 21 regressions in 130+ agent-assisted patches and built plugins to catch them.
- [Catching Bugs Before They Land](https://engineering.fb.com/2026/10/29/security/catching-bugs-before-they-land-jittestings-human-on-the-loop-approach-at-full-scale/). Meta's LLMs write tests meant to fail on risky diffs, and they caught 74 serious privacy bugs in the first half of 2026.

Agent swarms

- [The surprising leadership dynamics in agent swarms](https://www.raindrop.ai/blog/agent-swarm-leadership). Over 2,160 games, many agents gave orders but few changed anyone's behavior.
- [We ran AI agent swarms in Minecraft and Mindustry](https://labs.ycombinator.com/projects/games/index.html). YC gave 50 agents three hours to build a civilization and got a "sole fertilizer operator".
- [Formalizing the Enormous Theorem](https://axiommath.ai/research/the-enormous-theorem-formalized). Swarms wrote about 43.1 million lines of Lean in 24 days to check the Classification of Finite Simple Groups.

Running agents

- [TokenEconomizer](https://github.com/microsoft/TokenEconomizer). A plugin that remembers repo facts between sessions and reports 18.4-30.9% lower mean cost.
- [OpenShell](https://github.com/NVIDIA/OpenShell). NVIDIA's sandbox runtime adds credentials only on requests to approved endpoints, so the agent never holds them.
- [Making every harness durable](https://vercel.com/blog/making-every-harness-durable). Vercel logs every model and tool call so a new function can resume a dead turn.

Models

- [Le Chonk: Built for Coders, Trusted by Defenders](https://mistral.ai/news/mistral-large-4-oss/). Mistral published the weights of its 1-trillion-parameter model.
- [Introducing Flint](https://recursive.com/updates/introducing-recursive-flint). Recursive's 40B model activates 2.5B parameters per token and runs at over 125 tokens per second on an M4 Pro MacBook Pro.
- [Apple's 20B On-Device Model Uses Just 2GB of Memory](https://www.airealist.ai/p/exploring-apple-on-device-model). It reads only the parts it needs from flash.
