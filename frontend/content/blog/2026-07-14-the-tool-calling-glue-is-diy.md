---
title: "The tool-calling glue is coming from GitHub, not labs"
description: "A cost-cutting Claude Code orchestrator, a geospatial SQL skill, and a Claude-Codex review loop, all built by individuals, not a model vendor's product team."
slug: the-tool-calling-glue-is-diy
topic: tool-calling
date: 2026-07-14
articles:
  - https://github.com/Nanako0129/pilotfish
  - https://github.com/dekart-xyz/geosql
  - https://aimaker.substack.com/p/claude-code-workflow-setup
---

None of this week's three most interesting tool-calling projects came out of
a model vendor's blog. All three are solo or small-team efforts stitching
Claude, Codex, and cheaper models together through skills, subagents, and
MCP — the parts of the stack Anthropic and OpenAI ship as raw primitives but
don't finish for you.

[Pilotfish](https://github.com/Nanako0129/pilotfish) packages a pattern
Anthropic benchmarked but never shipped as a product: let Fable 5 plan and
review inside your main Claude Code session, and hand the actual execution to
cheaper Sonnet or Haiku subagents. On BrowseComp, that combination lands at
86.8% accuracy against Fable-alone's 90.8% — roughly 96% of the performance
for 46% of the cost. Pilotfish's contribution is packaging that as a handful
of fixed roles and a one-prompt installer, rather than a sprawling catalog of
agents. The catch shows up more in Anthropic's own write-up than in
pilotfish's docs: Fable's edge isn't the checklist work you can hand off,
it's noticing something's wrong when nothing on the checklist says so, and
that doesn't delegate to a cheaper model. If your Claude Code bill is the
actual problem, try it. If you're leaning on Fable for judgment calls, keep
it in the loop instead of behind one.

[GeosQL](https://github.com/dekart-xyz/geosql) turns Claude or Codex into a
geospatial analyst that writes real PostGIS, BigQuery, and Snowflake SQL
instead of guessing table names: it explores your warehouse schema first,
dry-runs BigQuery queries against a 10 GiB cap before executing them, and
renders results on a map so the agent can catch a geometry mistake a
text-only review would miss. That map-in-the-loop step is the actual idea —
the project's own comparison shows task success far lower without it. Worth
flagging: a commenter on the project's Hacker News thread pointed out that
the eval chart and the surrounding prose don't agree, a graph showing single
digits next to text claiming success across the board. It's trending on
GitHub regardless, and the underlying idea — let the agent see its output,
not just describe it — generalizes well past geospatial data.

[The AI Maker's write-up](https://aimaker.substack.com/p/claude-code-workflow-setup)
on wiring Codex into a Claude Code workflow is less about one tool than about
where MCP is actually landing a year in: as the connector to a handful of
external systems, with skills doing the cheap, repeatable orchestration
around them. A community project, ching-kuo's claude-codex, shows the shape
concretely — Codex reviews Claude's diffs over MCP and hands back only a
structured verdict, capped at three fix-and-recheck rounds, specifically so
a second opinion doesn't cost more than the bug it catches. Small pattern,
but it's the same one running through all three stories: nobody's waiting
for Anthropic or OpenAI to ship the glue between their own tools, so people
are writing it themselves in skills and thin MCP wrappers.

Of the three, pilotfish is the one I'd actually install — the cost math
holds up, and it doesn't ask me to trust a chart that contradicts its own
text. GeoSQL's map-in-the-loop trick is the one I'd steal for something
outside geospatial work, once someone reconciles those numbers.
