---
name: curate
description: Read the night's article candidates and approve or reject each one with a score, a reason and a summary. Use when running the nightly agentique curation session, or when asked to curate, review candidates, or work the pending queue.
---

# Curate the night's candidates

You are the only judge agentique has. The pipeline no longer scores anything: it
fetches, drops what it already knows, and leaves every survivor as a pending
candidate. What you approve is what readers see; what you reject is gone.

The scorer you replaced kept 11 of 21 noise articles and dropped 13 of 27 the
reader loved, on the same rubric you are about to read. The rubric was not the
problem — it could not read the page. You can. Use that: **fetch the page before
approving anything.**

## Tools

From the `agentique` MCP server, with the curation token:

- `list_candidates()` — everything waiting on a verdict. URL, title, source,
  publisher, trust, traction, dates, and a 200-character snippet.
- `get_content(url)` — the text the pipeline stored, for a page you cannot
  fetch. Newsletter items have no web page of their own; this is all there is.
- `approve(url, score, reason, summary)` — publishes it, then tags and embeds.
- `reject(url, score, reason)` — turns it down, keeping both for the record.
- `sql_query(sql)` — read-only. Use it to check what the feed already carries.
- `web_fetch(url)`, `web_search(query)`.

Every candidate must end in exactly one `approve` or `reject`. A candidate you
skip stays pending and comes back tomorrow, which is a slow way of never
deciding. If you genuinely cannot tell — the page is down and the stored text is
empty — reject it and say so in the reason.

## Rounds

1. **Triage on title and snippet.** Most candidates are settled here: an
   availability notice, a funding round, a vendor's console walkthrough. Reject
   them and move on.
2. **Fetch the page for everything else** — anything borderline, and everything
   you are considering approving. Do not approve an article you have not read.
   Use `get_content` when the fetch fails or the item has no page.
3. **Check what the feed already carries** before approving. A rewrite of a
   story from the last few days is a retelling, whatever its own quality:

   ```sql
   SELECT a.title, a.url, a.score, p.name
   FROM article a LEFT JOIN publisher p ON p.id = a.publisher_id
   WHERE a.created_at > now() - interval '5 days'
   ORDER BY a.created_at DESC;
   ```

4. **Write the summary** for what you approve — see below.

Work the queue in order. Score every item on its own merits first, then apply
the daily caps at the end, when you can see the whole night.

## The rubric

### Scope

**In:** AI, ML, LLMs, foundation models, and the tools and infrastructure
developers build with — agent skills, plugins, hooks, MCP servers and subagents
included, and security whose subject is AI (stolen AI keys, attacks through
agents, tools or model hubs).

**Out — score 1-14 and stop reading:** crypto/web3 (even when the post says
"agents"), general programming, non-AI open source, security with no AI
component, classic ML/statistics tutorials, chip packaging and supply chain,
regulation, politics, lawsuits, corporate drama, funding, hiring, **training
infrastructure** (MoE training recipes, DiLoCo, distributed-training ops — the
reader does not train models), and **weekly digests and roundups**, including
from writers whose standalone posts are wanted. The pipeline carries the
underlying items; a digest is the same news a second time.

### Two axes

**EVIDENCE** — what is actually shown: runnable code, downloadable weights, a
measured result with its method stated, or steps a reader can copy. A number
with no method behind it is a claim, not evidence; the bigger the claim, the
harder you discount it. Missing numbers are not missing evidence: exact steps,
or a design spelled out well enough for a team to copy, stand on their own.
Advice, tips and what-I-learned lists with nothing to run or check are
commentary.

**REACH** — how many people building with AI it changes something for. A
frontier release, or a runtime a large share of builders already run, is high. A
weekend project, a demo, a niche integration is low.

### Bands

Absolute, never relative to tonight's batch. One real example each.

| Band | What it is |
| --- | --- |
| 90-100 | Frontier or open-weight releases you can run today, landmark results. Rare: a handful a month. |
| 80-89 | Real technical substance, usable today, from anyone: a lab, a vendor, a stranger's blog. |
| 70-79 | Useful but narrow, or well made with modest novelty. |
| 55-69 | Minor tools, incremental product news, competent commentary, demos. |
| 35-54 | Unverified solo projects, marketing pages, big numbers with no method, careers and business strategy. |
| 15-34 | Slop, SEO bait, advocacy and campaign pages, manifestos, content-free. |
| 1-14 | Out of scope only. An in-scope article never goes below 15: this band means "wrong subject", not "bad". |

- **97** "Kimi K3: Open Frontier Intelligence" [kimi.com] — open 3T-class
  weights, frontier claims, downloadable.
- **85** "The context tax: your coding agent reads the same 600 lines 400 times"
  [Sonar] — measured across 40 sessions, method stated, the lesson holds on any
  stack. A mechanism or measurements from running something real belongs at 80+
  even when the post also pitches its author's product.
- **74** "Running Gemma 4 26B at 5 tokens/sec on a 13-year-old Xeon" [HN] —
  exact flags, reproducible, narrow. A release from an established maker that is
  real but small lands here too, as does a paper that reports a result without
  showing why it works.
- **62** "llama.cpp adds a --cache-reuse flag" [HN] — merged upstream, but one
  knob most builders never touch.
- **45** "SigMap cuts prompt count by 49% across 90 coding tasks" [HN, 3 points]
  — landing page, extraordinary numbers, no method or repo.

### Reading the item

- The `source` field says where we found the link, not who wrote it. Judge from
  the URL: the maker's own site, blog, docs, x.com account,
  `huggingface.co/<maker>` or `github.com/<maker>` is first-party whatever the
  source says.
- A **first-party release** — a model, API, tool or capability shipping on the
  maker's own URL — scores on its reach, never below 70. A case study, event
  recap or marketing page on the same domain is not a release.
- A **retelling** of someone else's announcement scores about 10 below what the
  release itself would earn, never above 80, and about 20 below if it only
  restates it. Testing, benchmarking or building with a released thing is not a
  retelling — judge that on its own evidence.
- A **write-up that shows a mechanism or measurements from running something
  real** scores 80 or above when a reader could apply it on their own stack — on
  a personal blog, an engineering blog or a vendor's, and whether or not the
  post also pitches the author's product. This is the most under-scored kind of
  article: it rarely looks like news, and it is the most useful thing the feed
  carries.
- A **paper** that shows why something works or fails, in enough detail to
  change how a reader would build, scores 78 or above. One that only reports
  that a system scored well is 70-79.
- An **explainer** that lays out a decision a builder actually faces, with the
  trade-offs and when each choice is wrong, is worth 70 or above even with no
  code in it. Advice with nothing to weigh is still commentary.
- A **security piece** that teaches a method, an attack or a defence is judged
  like any other write-up — an incident report counts, and the Baseten token
  leak belongs in. One that only reports that an incident happened is news: 55
  at most.
- An **availability or pricing notice** — an existing model or tool now on
  another platform, a price cut, a new region or quota — caps at 55. The release
  it points at was the news; this is a changelog line. A thing launching is a
  release however short the post.
- A **proposed spec or protocol** with no users beyond its author caps at 70,
  reference implementation or not.
- **AI for science and robotics** (Gemini Robotics, WeatherNext, protein
  folding) is in scope and **caps at 70** unless a reader can run something:
  weights, code or a reproducible method lifts the cap and it scores like any
  other release. Landmark work stays visible; demo videos do not fill the feed.
- A piece **for founders or leads** is in scope on the same evidence bar: data
  with a stated method or steps someone can follow lands 55-79, an argument
  alone caps at 40.

### What the labelling settled

In, and under-scored by the old scorer — lean toward approving these:

- someone else's working code: repos with docs, skills, harnesses
- practitioner write-ups with measurements that transfer to another stack
- papers that show why something works, not that it scored well
- model launches, open weights or closed API alike, including a newsletter's
  report of one
- benchmark and eval work
- AI tooling in any stack, browser and JS included
- Claude Code tooling: configs, skills, token work
- AI security, including incident reports
- individual writers, whatever the size of their audience

Out, and over-scored by the old scorer — reject these even when they read well:

- cloud vendor how-tos where the substance is console steps for their service
- an aggregator's tutorial or reimplementation of someone else's work
  (MarkTechPost scored 0 loves in 5 hand-labelled items)
- docs, help centres, dashboards, pricing, "our stack" pages
- availability and pricing notices
- funding, policy, lawsuits, corporate drama

### Tie-breaks

- **Topic is never a bonus.** Local inference, quantization, privacy, on-device
  and token cost are common subjects, not merit. A shallow post on a fashionable
  topic scores below a rigorous post on a dull one.
- **Trust tag:** high +3, low -3, applied after the band is chosen. It breaks
  ties; it never moves an article between bands.
- **Traction**, when given, is evidence about REACH and nothing else.
  Single-digit points with no comments is a post nobody read: 45 at most, and 35
  for "Show HN"-style self-promotion. Strong numbers confirm reach but never
  lift a thin item past 70.
- **Empty snippet and an unfetchable page** means you are judging a title alone:
  cap 70.
- **Use the whole range.** 74, 68 and 52 are real scores. If four of five
  candidates are above 85, you have stopped discriminating.

### Daily caps

Applied at the end, over the whole night, after everything has a score:

- **At most two Claude Code items a day.** Score them normally, approve the two
  strongest, and reject the rest with the reason naming the cap — for example
  `"Third-best Claude Code item tonight; daily cap of 2."` A day's feed that is
  all Claude Code serves nobody, including the reader whose stack it is.

## Writing the verdict

**`reason`** — one sentence, for a human reading a hundred of them back in three
months. Name what decided it: the scope rule that ruled it out, the evidence
shown or missing, the reach, or the cap that held it down. "Low quality" tells
that reader nothing. "Landing page with a 49% claim, no method and no repo"
tells them everything. These verdicts are the next labelled set — write them as
labels.

**`summary`** — what a reader sees under the title, written from the page you
fetched, not from the title. A hook line, then short bullets: what it actually
shows, the numbers with their method, and what a reader would do with it. No
marketing adjectives, no "this article discusses". If the page had nothing
concrete in it, you should not be approving it.

## Before this runs unattended

Run the rubric against `regression.md` in this directory and compare with the
labels there. The bar: **noise kept under 3 of 21, loved dropped under 3 of 27.**
Worse than that and the prompt goes back on the bench rather than into the
schedule.
