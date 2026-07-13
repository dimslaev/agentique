---
title: "The real MCP trend: narrower tools, not smarter agents"
description: "Five new agent tools this week trade autonomy for narrow, deterministic APIs into codebases, geodata, Office docs, and video timelines."
slug: narrow-tools-beat-smarter-agents
topic: tool-calling
date: 2026-07-13
articles:
  - https://github.com/enola-labs/enola/tree/main
  - https://github.com/dekart-xyz/geosql
  - https://github.com/iOfficeAI/OfficeCLI
  - https://github.com/ronak-create/FableCut
  - https://github.com/Nanako0129/pilotfish
---

I keep seeing the same shape in this week's tool-calling releases, and it's not the shape I expected. Everyone talks about agents getting more autonomous. What actually shipped this week is agents getting *less* freedom, in a good way: narrower, deterministic interfaces into specific domains, instead of raw file access and hope.

[Enola](https://github.com/enola-labs/enola/tree/main) is the clearest case. It's a local MCP server that parses your codebase once and builds an actual dependency graph — modules, types, routes, call chains — so your agent stops re-discovering your architecture by grepping every session. The README's pitch is "run it twice on the same commit and you get the same answer, every run," which is the whole point: an agent guessing at your codebase's shape from search results is not the same as an agent that can call `find_path` or `impact_analysis` against a real graph. I cloned it to check this wasn't a wrapper around an LLM prompt — it's a genuine ~29MB Go project with dedicated extractor, linker, and diff packages, and support for 14+ languages. That's real infrastructure, not vibes.

The same pattern shows up in narrower form elsewhere. [GeoSQL](https://github.com/dekart-xyz/geosql) turns Claude, Codex, or Copilot into a geospatial analyst — it discovers your PostGIS/BigQuery/Snowflake schema instead of guessing column names, dry-runs queries against a billing cap, and renders results on a map so the agent can visually catch a bad geometry before you do. [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI) does the same for Word, Excel, and PowerPoint: path-based addressing like `/slide[1]/shape[2]` instead of an agent fumbling through raw XML. And [FableCut](https://github.com/ronak-create/FableCut) exposes a browser video editor's entire timeline as a JSON project file an agent can patch directly over MCP or a REST API — cut to beat markers, place captions, all without touching a video codec. None of these make the agent smarter. They make the domain legible, which turns out to matter more.

The other side of this is [Pilotfish](https://github.com/Nanako0129/pilotfish), which is about who does the calling, not what gets called. It's an orchestration layer that routes work across model tiers by role rather than by name — a frontier model plans and verifies, cheaper models execute the mechanical parts. Its README cites Anthropic's own benchmark of a frontier-orchestrator-plus-cheaper-worker setup landing at 96% of all-frontier performance for 46% of the cost on BrowseComp, and a separate community test (Developers Digest) measuring the same pattern at 58-74% cost savings depending on which worker tier you pick. I can't verify Anthropic's internal number myself, but the shape — spend the expensive model on judgment, not execution — is the same one showing up in every narrow-tool release above: don't make the model do more work, make the work it has to do smaller.

If I tried one thing from this list, it'd be Enola on my own repo before the next big refactor — a dependency graph an agent can actually query beats one it has to re-guess every session.
