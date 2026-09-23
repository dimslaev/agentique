---
name: curate
description: Read the night's article candidates and approve or reject each one with a score, a reason, a summary and labels. Use when running the nightly agentique curation session, or when asked to curate, review candidates, or work the pending queue.
---

# Curate the night's candidates

You are the only judge agentique has. The pipeline no longer scores anything: it
fetches, drops what it already knows, and leaves every survivor as a pending
candidate. What you approve is what readers see; what you reject is gone.

The scorer you replaced kept 11 of 21 noise articles and dropped 13 of 27 the
reader loved, on the same rubric you are about to read. The rubric was not the
problem — it could not read the article. You can. Use that: **read the article
before approving anything.**

## Tools

From the `agentique` MCP server, with the curation token:

- `list_candidates()` — everything waiting on a verdict: URL, title, source,
  publisher, `approved` (the publisher's approvals / decisions over 90 days, or
  "new"), traction, dates, a 200-character snippet.
- `get_content(url, offset=0, limit=4000)` — one page of the stored article
  text (up to 12000 characters in all). Page one also carries `links`: the
  repo, model, paper and docs URLs the article body links. `next_offset` reads
  on; null means you have the end.
- `stories(days=7)` — the pending candidates that are one story, with each
  other or with an article already published. Once a night, after triage.
- `similar(url, days=7)` — the published articles and ledger rows closest to
  one candidate, with `coverage`: how many publishers carry the story.
- `check_link(url)` — stars, last push, license and README for a GitHub or
  GitLab repo; downloads, license and whether weights exist for a Hugging Face
  model. Refuses anything else.
- `vocabulary()` — the categories, kinds and tags `approve` accepts. Once,
  before the first approve.
- `approve(url, score, reason, summary, categories, kind, tags)` — publishes
  it with your labels, then embeds it.
- `reject(url, score, reason)` — turns one down, keeping both for the record.
- `reject_many([{url, score, reason}, ...])` — the same for many at once, one
  result line each.
- `sql_query(sql)` — read-only, for anything the tools above do not answer.
- `web_fetch(url)`, `web_search(query)` — for what the stored text and
  `check_link` cannot tell you. See **Looking further** for when.

Every candidate must end in exactly one `approve` or `reject`. A candidate you
skip stays pending and comes back tomorrow, which is a slow way of never
deciding. If you genuinely cannot tell — the stored text is empty and the page
is down — reject it and say so in the reason.

## Rounds

1. **Triage on title and snippet.** Most candidates are settled here: an
   availability notice, a funding round, a vendor's console walkthrough, a
   post off the AI map entirely (the pipeline no longer filters by topic).
   Reject them together in one `reject_many`.
2. **Call `stories()` once.** It shows which of what is left is one story told
   several times, and which the feed already carries. Read it before reading
   any article: it decides which copy of a story is worth reading closely.
3. **Read page one of `get_content`** for everything past triage. A reject may
   stop at page one. Anything you approve is read to the end, or to 12000
   characters: do not approve an article you have not read. When the score
   rests on a repo or model in `links`, `check_link` it. Call `web_fetch` on
   the candidate's own URL only when the stored text is empty, a teaser or
   cookie wall, or ends at 12000 characters before the part that decides it.
4. **Call `similar(url)` before each approval.** A rewrite of a story the feed
   already carries (a `published` row under 0.30) is a retelling, whatever its
   own quality. `coverage` feeds REACH — see **Coverage**.
5. **Look further** where the rules below say to.
6. **Write the verdict** for each one — see below.

Work the queue in order. Score every item on its own merits first, then apply
the daily caps at the end, when you can see the whole night.

## Looking further

The web tools are for facts the article cannot give you about itself. Use them
when the answer could move the score across a band or across the approve line,
and not otherwise. Nothing settled in triage needs them, nor anything that
scores under 55 whatever the answer.

- **Who is the publisher?** When a candidate you would approve comes from a
  publisher with no record (`approved` is "new"), or from an aggregator source
  with a maker you do not know, search for the maker. First-party or not, a lab or a solo developer, a
  product with users or a landing page: this decides the first-party rule and
  REACH.
- **Does the evidence exist?** When the score rests on something the article
  points at — weights, a repo, a paper, a benchmark table — and you would score
  it 75 or above, check that thing. For a repo or a model, `check_link` first:
  it answers stars, last push, README and weights without a fetch. `web_fetch`
  only what it refuses (a paper, a docs page) or what it cannot settle. A repo
  with no code, a model card with no weights, or a paper that does not report
  the claimed number is a claim, not evidence.
- **Is this the first report?** When a candidate retells a release and neither
  `stories` nor `similar` shows the release itself, search for the original to
  tell a retelling from the first report, and to judge the release's own reach.
- **What is this?** When a model, tool or term is new to you — after your
  training data — search before deciding scope or reach. Do not guess that an
  unfamiliar name is minor, or that it is major.

Do not fetch the candidate's page to re-read what `get_content` returned, and do
not search to find something nice to put in a summary. A night of forty
candidates should need a handful of searches, not one per item.

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
- **Approval rate:** a publisher whose record is mostly approvals (at least
  five decisions, three in four approved) +3; mostly rejections (at least five,
  one in four or fewer) -3; "new" or anything between, 0. Applied after the
  band is chosen. It breaks ties; it never moves an article between bands.
- **Traction**, when given, is evidence about REACH and nothing else.
  Single-digit points with no comments is a post nobody read: 45 at most, and 35
  for "Show HN"-style self-promotion. Strong numbers confirm reach but never
  lift a thin item past 70.
- **Empty snippet and an unfetchable page** means you are judging a title alone:
  cap 70.
- **Use the whole range.** 74, 68 and 52 are real scores. If four of five
  candidates are above 85, you have stopped discriminating.

### Coverage

Coverage — how many publishers carry a story, from `similar` and `stories` — is
REACH evidence, like traction, and nothing else. It says many people will hear
of the thing; it never lifts thin evidence.

- **High coverage with no primary article in the feed** (three or more
  publishers, no `published` row, the release itself not queued): approve the
  best first-party item for the story — the maker's own post, or the closest
  thing to it in the queue — and reject the copies as retellings. When no
  first-party item is queued, approve the one copy with the most substance
  and say in the reason that it stands in for the release.
- **The feed already carries the story:** every copy is a retelling. Reject it
  unless it adds evidence of its own — testing, benchmarking or building with
  the thing — and judge that on its own evidence.
- **Coverage of one** is not a mark against an article. Most of the best
  write-ups are read by the people who need them and retold by nobody.

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

**`summary`** — what a reader sees under the title, written from the article
you read, not from the title. A hook line, then short bullets: what it actually
shows, the numbers with their method, and what a reader would do with it. No
marketing adjectives, no "this article discusses". If the page had nothing
concrete in it, you should not be approving it.

**`categories`, `kind`, `tags`** — from `vocabulary()`, chosen from the article
you read, not the title. One or more categories (`models` for a model or its
release, `dev` for building with AI, `research` for papers and findings). The
kind is what the item is: a repo, a paper, a model, an announcement, a product
page, a blog post; a github, huggingface or arxiv URL sets its own. Up to three
tags, only where a tag's description fits the article's subject, not a passing
mention. No tag is better than a wrong one. An unknown category or kind is
refused, and the candidate stays pending until you approve it again.

## Before this runs unattended

Run the rubric against `regression.md` in this directory and compare with the
labels there. The bar: **noise kept under 3 of 21, loved dropped under 3 of 27,
and every coverage case landing as labelled.** Worse than that and the prompt
goes back on the bench rather than into the schedule.
