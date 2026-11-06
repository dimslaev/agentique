---
title: The most interesting stuff this week
description: Agent code review, an open model that built Firefox exploits from unreleased fixes, and swarms that follow prompt order.
topic: most-interesting-this-week
sources: false
---
Code review

- [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/). Agents review first, then humans, and reverts fell 40%.
- [AI agent fixed the bug, but what else did it change?](https://blog.trailofbits.com/2026/10/21/your-ai-agent-fixed-the-bug-but-what-else-did-it-change/) Agent patches caused 21 regressions in 130 merges.

Security

- [AI can turn security fixes into working exploits before users receive an update](https://epoch.ai/publications/open-weight-models-patch-gap). An open model built Firefox exploits from unreleased fixes.
- [Backdoor in Claude Code for VS Code extension on the Cursor Marketplace](https://phorion.io/blog/offical-claude-code-vsx-compromise/). Two Cursor Marketplace extension versions opened an SSH backdoor.

Running agents

- [The surprising leadership dynamics in agent swarms](https://www.raindrop.ai/blog/agent-swarm-leadership). Agent order in the prompt decides who leads a swarm.
- [We ran AI agent swarms in Minecraft and Mindustry](https://labs.ycombinator.com/projects/games/index.html) Swarm agents defer to whoever is listed first.
- [TokenEconomizer: Experience-Driven Black-Box Cost Control for Coding Agents](https://github.com/microsoft/TokenEconomizer). Remembering repo facts cuts agent costs up to 31%.
- [The AI cost of JavaScript frameworks](https://nolanlawson.com/2026/10/28/the-ai-cost-of-javascript-frameworks/) Agent build cost ranged from $2.67 to $4.97 by framework.

Models

- [Le Chonk: Built for Coders, Trusted by Defenders.](https://mistral.ai/news/mistral-large-4-oss/) Mistral Large 4 weights are out under a modified MIT license.
- [Leaking Muse's Charter, Meta's model spec](https://www.lesswrong.com/posts/TJGPL5FAk9sCioPbE/leaking-muse-s-charter-meta-s-model-spec). Meta's Muse charter rebuilt from the model's own outputs.
- [Astra can read and write weights to improve Qwen](https://rikiyat.github.io/blog/weight-space-programming/). Editing 0.016% of Qwen's weights fixed its reasoning loops.
