---
title: "Orchestration is becoming something you install"
description: "A Go SDK for agent backends, NVIDIA's leaner RL trainer, and Kimi's CLI baking in subagents and memory - three teams shipping what used to be bespoke."
slug: orchestration-is-becoming-something-you-install
topic: orchestration
date: 2026-08-03
articles:
  - https://github.com/grafana/ai-sdk
  - https://www.marktechpost.com/2026/08/01/nvidia-ai-releases-molt-a-pytorch-native-agentic-reinforcement-learning-framework/
  - https://www.marktechpost.com/2026/07/28/building-non-interactive-agentic-coding-workflows-with-moonshot-ais-kimi-cli-jsonl-streaming-testing-and-session-memory/
---

Three weeks ago I wrote that the [tool-calling glue was coming from individual
builders on GitHub, not vendors](/blog/the-tool-calling-glue-is-diy/). This
week's stories are the counter-case: a company, a lab, and a model vendor each
shipping the packaged version of exactly the duct tape people were hand-rolling.
Same pattern across three different altitudes - app backend, RL training
infra, coding-agent pipeline - the bespoke orchestration layer is turning into
something you `go get` or `pip install`.

[Grafana's ai-sdk](https://github.com/grafana/ai-sdk) is the clearest case: an
open-source Go SDK for building AI backends that stream responses, call tools,
and emit schema-validated structured output, wire-compatible with Vercel's
`@ai-sdk/react` hooks so a Go service can drive a React chat UI without a
translation layer in between. It's explicitly modeled on Vercel's TypeScript AI
SDK, and Hacker News treated it that way - the top comment on the launch
thread asked flatly what this provides over just using Vercel's SDK, and
another pointed out it skips resumable streaming after a dropped SSE
connection and has no multi-device story, the two things that actually hurt
once you try to build something durable on top of a chat SDK. Fair criticism,
but it's aimed at a real gap: if your backend is Go and you've been hand-writing
SSE parsers and JSON-schema tool definitions, this replaces that boilerplate
even with the rough edges HN flagged.

[NVIDIA's Molt](https://www.marktechpost.com/2026/08/01/nvidia-ai-releases-molt-a-pytorch-native-agentic-reinforcement-learning-framework/),
open-sourced by NeMo Labs, does the same thing for a much heavier stack:
training models where the reward comes from an external checker - a test
suite, a tool call's output, an LLM-as-judge - instead of a static label. The
paper's own line count is the whole pitch: about 8,600 lines end to end,
against roughly 62,000 for verl and 25,000 for slime, while still scaling to
trillion-parameter MoE models at throughput the authors report as comparable
to Megatron-based stacks. The design guarantee that sold me - the trainer
never sees a token the model didn't generate - closes off a class of silent
bugs where a rollout gets corrupted and the run just quietly trains on garbage.
The tradeoff is real narrowness: one training backend (FSDP2), one serving
engine (vLLM), no multi-node production hardening. It's a lab's tool for
running an agentic RL experiment without first standing up a Megatron cluster,
not a verl replacement.

[Kimi's CLI](https://www.marktechpost.com/2026/07/28/building-non-interactive-agentic-coding-workflows-with-moonshot-ais-kimi-cli-jsonl-streaming-testing-and-session-memory/)
takes the same move furthest into product territory: built-in coder, explore,
and plan subagents, JSONL event streams you can pipe into a script, and
session files that persist context across restarts, so the whole thing runs
non-interactively in a pipeline instead of only as a chat loop you babysit.
Moonshot's backing model, K2.7-Code, is priced around $0.95/$4 per million
tokens against Sonnet's $3/$15, which is the actual draw - one Hacker News
commenter rated its raw capability as "below Sonnet and Opus," and it's
documented as struggling on domain-specific tasks. I'd reach for it on
high-volume, mechanical jobs - bulk test generation, a boilerplate migration
across hundreds of files - where cost per run beats best-in-class judgment,
and stick with a stronger model for anything that needs to get the tricky part
right the first time.

None of these are finished products - HN's complaints about Grafana's SDK and
Molt's narrow backend are both real limits, not marketing. What I'd actually
do this week is stop writing another SSE handler by hand and see how far
ai-sdk gets me first.
