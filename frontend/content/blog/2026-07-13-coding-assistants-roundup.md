---
title: "Coding Assistants: New Models Land, Claude Code Tooling Expands"
description: "Kimi K2.7 lands in GitHub Copilot as Claude Code tooling grows and teams reckon with agentic coding costs and code quality."
slug: coding-assistants-roundup
topic: coding-assistants
date: 2026-07-13
articles:
  - https://github.blog/changelog/2026-07-01-kimi-k2-7-is-now-available-in-github-copilot/
  - https://x.com/Scobleizer/status/2076215305085612471
  - https://joseparreogarcia.substack.com/p/claude-code-planning-mode-thinking-levels-goal-mode
  - https://linas.substack.com/p/claude-fable-5-agentic-os-guide
  - https://prosperinai.substack.com/p/claude-code-artifacts-guide
  - https://lovable.dev/blog/85000-in-tokens-later-scaling-agentic-coding-at-lovable
  - https://sigmap.io/
  - https://blog.okturtles.org/2026/07/short-leash-ai-method/
  - https://joeyh.name/blog/entry/no_LLM_code_in_dependencies/
---

Two threads run through coding-assistant news this week: frontier code models are showing up inside the tools developers already use, and the ecosystem around those tools is maturing fast enough that teams are now writing up hard numbers on what agentic coding actually costs and breaks.

## New models land where developers already work

Moonshot's Kimi K2.7 Code is now [generally available in GitHub Copilot](https://github.blog/changelog/2026-07-01-kimi-k2-7-is-now-available-in-github-copilot/), putting an open-weight coding model directly alongside Copilot's existing options rather than requiring a separate integration. The same model is also turning up as infrastructure: [Lithos, a new agentic inference engine, is built on top of Kimi K2.7](https://x.com/Scobleizer/status/2076215305085612471), aimed at serving agentic coding workloads rather than general chat.

## Claude Code's toolkit keeps growing

Several posts this week dug into how to actually drive Claude Code well. One argues that [planning and goal modes matter more than thinking-level tuning](https://joseparreogarcia.substack.com/p/claude-code-planning-mode-thinking-levels-goal-mode) for getting reliable output on non-trivial tasks. A separate deep dive lays out [an "agentic OS" architecture built around Claude Fable 5](https://linas.substack.com/p/claude-fable-5-agentic-os-guide), treating the coding agent as a system to be designed rather than a chat window to be prompted. For developers newer to the tool, there's also a walkthrough on [building a first Claude Code artifact from system prompts and starter kits](https://prosperinai.substack.com/p/claude-code-artifacts-guide).

## The cost and quality reckoning

The more sobering thread is what agentic coding costs and where it breaks. Lovable published a detailed account of [what they learned scaling agentic coding after spending $85,000 in tokens](https://lovable.dev/blog/85000-in-tokens-later-scaling-agentic-coding-at-lovable), while [SigMap reports cutting prompt count by 49% across 90 coding tasks](https://sigmap.io/), a reminder that token efficiency is becoming its own optimization target alongside model quality. On the correctness side, the [Short-Leash method proposes tightly scoping what AI coding agents are allowed to touch](https://blog.okturtles.org/2026/07/short-leash-ai-method/) as a security practice, and one widely discussed post makes [the case for banning LLM-written code from dependencies entirely](https://joeyh.name/blog/entry/no_LLM_code_in_dependencies/), arguing supply-chain trust doesn't yet extend to agent output. Together they suggest the excitement over new models is being met with equally serious scrutiny of how they're used.
