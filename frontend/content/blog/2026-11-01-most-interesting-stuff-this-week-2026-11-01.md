---
title: The most interesting stuff this week
description: Agents reviewing code, swarms picking leaders by list order, and a 1-trillion-parameter open model.
topic: most-interesting-this-week
sources: false
---
Code review

- [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/). PRs doubled while reverts fell 40%.
- [AI agent fixed the bug, but what else did it change?](https://blog.trailofbits.com/2026/10/21/your-ai-agent-fixed-the-bug-but-what-else-did-it-change/) Agent fixes caused 21 regressions in 130 patches.
- [Catching Bugs Before They Land](https://engineering.fb.com/2026/10/29/security/catching-bugs-before-they-land-jittestings-human-on-the-loop-approach-at-full-scale/). AI-written tests caught 74 serious privacy bugs.

Agent swarms

- [The surprising leadership dynamics in agent swarms](https://www.raindrop.ai/blog/agent-swarm-leadership). Agents in swarms mostly ignore each other's orders.
- [We ran AI agent swarms in Minecraft and Mindustry](https://labs.ycombinator.com/projects/games/index.html). Swarms pick leaders by list order.

Running agents

- [GitLab Orbit is GA: Higher agent accuracy, lower token cost](https://about.gitlab.com/blog/gitlab-orbit-ga/). A code graph beat RAG for AI review.
- [TokenEconomizer](https://github.com/microsoft/TokenEconomizer). Remembering repo facts cuts agent costs up to 31%.
- [OpenShell](https://github.com/NVIDIA/OpenShell). Sandboxed agents never see your real credentials.
- [Making every harness durable](https://vercel.com/blog/making-every-harness-durable). Agents can now survive crashes mid-task.

Models

- [Le Chonk: Built for Coders, Trusted by Defenders](https://mistral.ai/news/mistral-large-4-oss/). Mistral released a trillion-parameter model you can download.
- [Introducing Flint](https://recursive.com/updates/introducing-recursive-flint). A strong coding model that runs on laptops.
- [Apple's 20B On-Device Model Uses Just 2GB of Memory](https://www.airealist.ai/p/exploring-apple-on-device-model). Apple's model fits in 2GB but scored last.
