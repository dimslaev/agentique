---
title: "The boring layer between parallel agents"
description: "A local merge queue for parallel Claude Code agents, a look at MCP vs A2A vs ACP, and why production agents are mostly deterministic code."
slug: the-boring-layer-between-parallel-agents
topic: orchestration
date: 2026-07-31
articles:
  - https://github.com/funador/claude-code-merge-queue
  - https://blog.bytebytego.com/p/mcp-vs-a2a-vs-acp-how-ai-agents-actually
  - https://blog.bytebytego.com/p/best-practices-for-building-ai-agents
---

Git worktrees solved the first problem with running several coding agents at once: each agent gets its own working directory, so it can't overwrite another agent's edits mid-task. Nobody solved the second problem — something still has to land all that finished work in order, without two agents pushing at the same moment and one silently losing. This week's stories aren't about agents getting smarter; they're about the plumbing underneath them getting less improvised.

## A merge queue, but for one developer

[claude-code-merge-queue](https://github.com/funador/claude-code-merge-queue) is a small, local tool: a FIFO queue that serializes landings so parallel Claude Code agents can't push-race each other or run redundant test suites at the same time. Merge queues used to be a problem enterprise teams solved with GitHub's built-in queue or a service like Mergify, because dozens of engineers were landing commits at once. Now one person running four or five agents locally hits the same failure mode alone, and the fix scales down to match: no server, the FIFO lives in a temp directory, and locks are crash-safe by PID liveness rather than a timeout, so a killed process doesn't leave a stale lock behind. There's a real limitation worth flagging: the only gate before something lands is your `checkCommand` passing — no human reviews the commit — so this is only as safe as your test suite, and a slow one becomes a throughput ceiling (a 3-4 minute suite caps you under 20 landings an hour). I'd try this the next time I have three-plus agents running against the same repo; I wouldn't trust it on a repo where the test suite doesn't actually catch regressions.

## MCP, A2A, ACP: pick the one for the actual shape of your problem

[A ByteByteGo explainer](https://blog.bytebytego.com/p/mcp-vs-a2a-vs-acp-how-ai-agents-actually) lays out the three-letter soup: MCP connects an agent to tools and data, A2A connects two independent agents as peers, and ACP was IBM's messaging-first take on the same peer problem — which has since folded into A2A under the Linux Foundation rather than surviving as its own spec. The distinction that matters in practice: if your "multi-agent" system is really one orchestrator calling sub-agents like functions, that's MCP with extra steps, not A2A. One benchmark paper (arXiv 2603.22823) found A2A used roughly 3.1x fewer tokens than MCP on complex multi-step queries — 11,318 versus 34,959 tokens — because A2A lets agents exchange task state directly instead of routing everything back through a central tool-calling loop. Reach for A2A only when you have genuinely separate agents that need to negotiate, not as a rebrand for orchestration you're already doing with MCP.

## Production agents are mostly if-statements

[This piece](https://blog.bytebytego.com/p/best-practices-for-building-ai-agents) argues, convincingly, that agents handling real production traffic depend on the model far less than demos suggest — most of the system is conventional deterministic code, with the LLM invoked at specific decision points. It leans on Dex Horthy's Twelve-Factor Agents framework: own your context window, keep control flow in code instead of letting the model decide when to stop, treat the model as stateless. That's the same instinct that pushed me to move agentique's LLM layer to [BAML](/blog/why-i-moved-agentiques-llm-layer-to-baml/) instead of ad-hoc prompt-and-parse — structure and control flow you own beat trusting the model to behave consistently, every time.

None of this week's three stories is about a new capability. They're about the unglamorous work of making agents you already have behave predictably at scale — which is a less exciting post than a new model release, and probably a more useful one to actually read.
