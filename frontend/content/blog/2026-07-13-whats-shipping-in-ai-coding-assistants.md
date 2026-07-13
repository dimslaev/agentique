---
title: "What I'd actually try from this week's coding tools"
description: "A wiki that writes itself, a 49% cut in prompts per task, and a code reviewer you can actually self-host."
slug: whats-shipping-in-ai-coding-assistants
topic: coding-assistants
date: 2026-07-13
articles:
  - https://factory.ai/news/wiki
  - https://www.humanlayer.dev
  - https://sigmap.io/
  - https://simonw.substack.com/p/have-your-agent-record-video-demos
  - https://github.com/miracodeai/mira
  - https://stacker.news/items/1510428
---

Most of what I read about coding assistants this week wasn't about writing
code faster. It was about the stuff around the code — the docs, the review,
the onboarding — finally getting automated too.

Start with [Factory AI's AutoWiki](https://factory.ai/news/wiki). It reads a
repo and writes a structured wiki that updates itself on every push. Factory
says it cut their own onboarding time, and I believe it — "someone should
update the wiki" is one of those chores that never actually happens, so
having it just happen is a bigger deal than it sounds.
[HumanLayer](https://www.humanlayer.dev) is going after the same problem
from a wider angle: an agentic IDE plus a collaboration layer across the
whole development cycle, claiming 2-3x faster shipping while keeping review
standards intact. Worth a look if your slowdown isn't writing code, it's
everything that happens after.

Then there's the efficiency angle, and this one surprised me:
[SigMap](https://sigmap.io/) cut prompt count by 49% and token usage by 97%
across 90 coding tasks, running fully offline. That's not a benchmark
leaderboard number, that's a number that shows up on your bill. I'd still
test it against your own tasks before trusting it fully, but it's the kind
of claim worth fifteen minutes of your time.

If I had to pick one thing to actually install this week, it's
[Mira](https://github.com/miracodeai/mira) — an open-source, self-hosted
code reviewer that runs on your own infrastructure and works with any model
through OpenRouter. If sending your diffs to a third party has ever given
you pause, this removes the reason to hesitate.
[Builderbot](https://stacker.news/items/1510428) is the other one I'd try:
tag it in Slack, and it branches, writes the code, opens the pull request,
and babysits CI until it's green. Good for the small fixes nobody wants to
context-switch for.

And a small detail that stuck with me: Simon Willison's release notes for
[sqlite-utils 4.0rc2](https://simonw.substack.com/p/have-your-agent-record-video-demos)
mention that Claude Fable wrote most of it, for about $149.25. Whatever you
think about that, it's now something people mention matter-of-factly, not as
a novelty. That's the actual shift happening here.
