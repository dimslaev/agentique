---
title: "Two of three 'orchestration' launches don't orchestrate"
description: "Microsoft's Orchard and NVIDIA's Molt train agentic models with RL, not build agent apps. CopilotKit's Channels SDK routes them - with a licensing catch."
slug: orchestration-training-not-routing
topic: orchestration
date: 2026-08-07
articles:
  - https://www.microsoft.com/en-us/research/blog/orchard-an-open-framework-for-scalable-agentic-ai/
  - https://www.marktechpost.com/2026/08/01/nvidia-ai-releases-molt-a-pytorch-native-agentic-reinforcement-learning-framework/
  - https://www.marktechpost.com/2026/08/04/copilotkit-open-sources-channels-sdk/
---

I pulled up this week's top three orchestration-tagged stories expecting agent
frameworks - the LangGraph, CrewAI, AutoGen kind of thing. Two of the three
turned out to be reinforcement-learning training rigs instead: infrastructure
for producing the agentic models that later get orchestrated, not tools for
doing the orchestrating. Only the third one actually routes agent traffic
anywhere, and even that one buries a catch under its MIT license.

Microsoft Research's [Orchard](https://www.microsoft.com/en-us/research/blog/orchard-an-open-framework-for-scalable-agentic-ai/)
is the clearest case. It's not a build-time framework - it's a
Kubernetes-native sandbox service for training and evaluating agentic models
with RL, the plumbing labs use to make a coding or browsing agent good at its
job before it ever runs inside something like Claude Code or Codex. Before
this, that meant hand-building sandboxes per task or renting from services
like E2B or Daytona; Microsoft's own numbers claim roughly 10x lower sandbox
cost against those two ($3,362 versus $7,078 for 128 parallel sandboxes over
240 hours). The headline result - Orchard-SWE hitting 69.7% on SWE-bench
Verified at around 3B active parameters, matching models Microsoft says are
10x larger - comes entirely from Microsoft's own paper. Three days after
release I couldn't find one independent benchmark check or even a skeptical
blog post about it anywhere. That's either too niche for outside scrutiny yet,
or nobody's tried to reproduce it. I'd wait for someone outside Redmond to run
the numbers before trusting the 10x claims.

NVIDIA's [Molt](https://www.marktechpost.com/2026/08/01/nvidia-ai-releases-molt-a-pytorch-native-agentic-reinforcement-learning-framework/)
is the same category - training agentic models with RL - but the interesting
bit is the size bet. The dominant agent-RL framework, verl, runs about 62,000
lines of code; Molt's entire RL path is roughly 8,600, small enough NVIDIA
argues one researcher, or a coding assistant, can hold the whole thing in
their head while swapping an advantage estimator or a rollout scheme. It also
targets a specific, nasty bug class: when the engine generating rollout
tokens and the engine training on them disagree about token boundaries, you
get silent corruption with no error thrown. Molt's fix guarantees the trainer
never sees a token the model didn't actually generate. I like that as a
design choice. But the framework's central claim - training performance
"statistically comparable" to the much larger Megatron-based alternative - is
self-reported, and one independent technical write-up I found flagged the
underlying paper as oddly vague about which mixture-of-experts model it
actually benchmarked. No Hacker News or Reddit thread on it yet either. Worth
watching, not yet worth trusting on the numbers.

[CopilotKit's Channels SDK](https://www.marktechpost.com/2026/08/04/copilotkit-open-sources-channels-sdk/)
is the one that actually orchestrates something at runtime: build an agent
once against AG-UI - CopilotKit's protocol for wiring an agent to a UI -
then run it inside Slack and Microsoft Teams without a separate integration
for each. No small thing if you've ever hand-rolled a Slack Bolt bot and a
Teams AI Library bot for the same assistant and watched them drift apart. The catch is in the fine print, not the
headline: the SDK itself is MIT-licensed, but every deployment routes through
CopilotKit's own "Intelligence" runtime, and CopilotKit's own docs say
production self-hosting of that runtime needs a paid Team or Enterprise plan.
"MIT-licensed, run anywhere" is true of the library; it's not true of the
thing that actually moves your messages. That's a familiar shape for
open-core companies, and worth checking before you build on it expecting a
fully self-hostable stack.

If I had to pick one to try, it's Molt - not because its numbers are proven,
but because a training framework small enough to read end to end beats one
that's 7x bigger and effectively unauditable. The other two I'd revisit once
someone outside the company that built them has actually run the benchmarks.
