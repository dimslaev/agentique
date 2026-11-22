---
title: The most interesting stuff this week
description: Big MoE models on laptops, picking a coding harness per model, and agent skills that revise themselves.
topic: most-interesting-this-week
sources: false
---
Local models

- [Edge0-145B: Frontier AI Capabilities on Your Own Computer](https://edge0.ai/blog/introducing-edge0-145b-frontier-ai-capabilities-on-your-own-computer). An open 145B MoE runs on a 48GB laptop.
- [Introducing Inkling 2 Mini](https://thinkingmachines.ai/news/inkling-2-mini). Looping its middle layers makes a 26B model fit laptops.
- [180B Parameters, 32GB of RAM: Pushing MoE Inference to the Limit with Transformers](https://huggingface.co/blog/moe-expert-streaming). Streaming experts from disk runs a 180B MoE on 32GB.

Coding agent setup

- [What is the best harness for each model?](https://runta.com/blog/introducing-frontierharness-eval-v1-1/) The best-value coding harness depends on which model you run.
- [External sandboxes for coding agents](https://simonwillison.net/2026/Nov/17/external-sandboxes-for-coding-agents/). Sandbox only the code the agent runs, not the agent.
- [OpenCode Browse: let coding agents use your logged-in browser](https://opencode.ai/product/browse). Agents work in your browser and hand logins back to you.
- [The Home Repo Pattern](https://www.aihero.dev/the-home-repo-pattern). Run agents from one repo that points to all others.

Agent skills

- [Perplexity's Self-Improving Skills](https://www.perplexity.ai/hub/blog/self-improving-skills). A skill revision ships only if it fixes replayed failures.
- [Deslop skill based on corpus-linguistics and psycholinguistics research](https://github.com/etodanik/deslop). One pass removing LLM prose tells helps, a second hurts.

Apps agents can drive

- [Klad, a paint app your coding agent can drive (source-available)](https://github.com/klad-app/klad). Agents paint with editable strokes, not an image model.
- [Doop: a multiplayer design canvas for people and AI agents](https://github.com/kgoedecke/doop). People and agents edit the same design canvas live.
