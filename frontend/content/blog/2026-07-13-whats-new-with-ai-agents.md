---
title: "Agents got cheaper. Someone wants to break them."
description: "Cheaper multi-step browsing, a 60% token cut for agent workloads, and a CTF built to compromise an agent in a microVM."
slug: whats-new-with-ai-agents
topic: agents
date: 2026-07-13
articles:
  - https://exa.ai/pricing
  - https://aidisruption.ai/p/superpowers-60-ai-optimizes-itself
  - https://declaw.ai/arena
  - https://www.firecrawl.dev/blog/research-index-launch
  - https://github.com/gi-dellav/speck/tree/main
  - https://thoughts.jock.pl/p/fable-5-efficiency-high-not-max-2026
---

Two things kept showing up in agent news this week: people trying to make
agents cheaper to run, and people trying to figure out how to stop them
from doing something nobody asked for.

On the cheaper side, Exa's [web-research API](https://exa.ai/pricing)
orchestrates smaller, cheaper models for the actual browsing and lets you
tune latency anywhere from 180 milliseconds to a second. If your agent is
currently burning a frontier model's context budget just to fetch and
summarize a webpage, this is a straightforward swap.
[Firecrawl's Research Index](https://www.firecrawl.dev/blog/research-index-launch)
does something narrower but more precise: a search index built specifically
for arXiv, hitting 53.3% recall at 32 cents a task. If your agent's job is
literature review, that's the kind of number worth paying attention to.

I liked [Superpowers 6.0](https://aidisruption.ai/p/superpowers-60-ai-optimizes-itself)
for a different reason — it has the agent optimize its own runs across
Claude Code, Codex, and similar tools, and the developer claims a 60% cut in
tokens and 50% faster builds. A [piece on routing Fable 5 workloads by task
complexity](https://thoughts.jock.pl/p/fable-5-efficiency-high-not-max-2026)
makes basically the same point in a more boring, more useful way: stop
sending every task to your biggest model. It's not a clever trick, it's just
something most people haven't gotten around to doing yet.

The one that actually stopped me mid-scroll was
[Declaw Arena](https://declaw.ai/arena) — a CTF-style challenge where you
try to compromise an agent running inside a microVM and pull a secret it's
supposed to protect. If your agents have real permissions in production,
I'd try this before someone else does it to you for real.

And if you'd rather define what your agent should do instead of
prompt-engineering it into behaving,
[Speck](https://github.com/gi-dellav/speck/tree/main) takes a
compiler-inspired approach — you write a spec, it generates the behavior.
Worth a look if you're tired of tweaking prompts and calling it
architecture.

None of this is a new framework. It's mostly people going back to agents
they already shipped and asking two honest questions: is this too
expensive, and can someone break it. Good questions to be asking yourself,
too.
