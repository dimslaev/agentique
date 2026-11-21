---
name: curate-articles
description: Read the night's article candidates and approve or reject each one with a score, a reason, a summary and labels. Use when running the nightly agentique curation session, or when asked to curate, review candidates, or work the pending queue.
---

# Curate the night's candidates

You are the only judge. What you approve readers see, what you reject is gone. Read an article before approving it.

## Tools

`agentique-admin` MCP: `list_candidates`, `read_article`, `find_duplicates`, `find_similar`, `check_repo`, `list_labels`, `approve_article`, `reject_articles`, `sql_query`, `web_fetch`, `web_search`.

Every candidate ends in one `approve_article` or `reject_articles`. If you can't tell (empty text, page down), reject and say so.

Copy URLs exactly as `list_candidates` gives them.

## Steps

1. Pre-filter on title and snippet. Reject availability notices, funding, vendor console walkthroughs and off-topic posts in one `reject_articles`.
2. Call `find_duplicates()` once, before reading. It shows stories told several times and ones the feed already has.
3. Read page one of `read_article` for the rest. Read to the end (or 12000 characters, `limit=12000`) before approving. `check_repo` when the score rests on a repo or model. `web_fetch` the URL only when the stored text is empty, a teaser, or cut off before the part that decides it. A fetch cut at `max_length` is our limit: fetch further, don't treat it as paywalled.
4. Call `find_similar(url)` before each approval. A `published` row under 0.30 means it's a repost.
5. Look further where **Looking further** says.
6. Apply daily caps at the end, over the whole night.
7. Write the verdicts.

## Say what you do

Tool calls are collapsed when the session is read back. Write short plain lines:

- Before each batch: what you're calling and why. Name the **Looking further** rule if one applies.
- After the pre-filter: rejects counted by reason. "Pre-filter: 96 rejected. 31 off the AI map, 18 vendor product posts, 14 digests..."
- Each decided item: verdict, score, title, deciding fact. "Approve 82 'Why Antigravity eats weekly quota': measured the 5-minute cache cliff with token counts."
- Surprises: tool errors, missed duplicates, rules pulling two ways.

No headers, no restating the rubric.

## Looking further

Search only when the answer could move the score across a tier or the approve line. Not for pre-filtered items or anything under 55 regardless. A night of 40 should need a handful of searches.

- **New publisher.** Approving from a publisher with `approved` "new", or an aggregator with an unknown creator: search for the creator. Decides the release-from-the-creator rule, reach, and `publisher_kind`.
- **Evidence.** Scoring 75+ on weights, a repo, a paper or a benchmark: check it. `check_repo` first, `web_fetch` what it can't answer. No code, no weights, or a paper without the claimed number is a claim.
- **First report.** A repost whose release neither `find_duplicates` nor `find_similar` shows: search for the original.
- **Unknown name.** A model, tool or term newer than your training: search before deciding scope or reach.

Don't fetch to re-read what `read_article` gave, or search for summary material.

## The rubric

### Scope

In: AI, ML, LLMs, foundation models, and the tools developers build with, including agent skills, plugins, hooks, MCP servers, subagents, and security about AI (stolen AI keys, attacks through agents, tools or model hubs).

Out, score 1-14 and stop reading:

- crypto/web3, even with "agents"
- general programming, non-AI open source, security with no AI part
- classic ML/statistics tutorials
- chip packaging and supply chain
- regulation, politics, lawsuits, corporate drama, funding, hiring
- training infrastructure: MoE recipes, DiLoCo, distributed-training ops, hosted training or fine-tuning platforms, even from the creator
- weekly digests and roundups, even from wanted writers

### Two axes

- **Evidence:** runnable code, downloadable weights, a measured result with its method, or steps a reader can copy. A number with no method is a claim, discounted more the bigger it is. Exact steps or a design clear enough to copy count without numbers. Advice and lessons-learned lists with nothing to run or check are commentary.
- **Reach:** how many AI builders it changes something for. Frontier releases and widely used runtimes are high. Weekend projects, demos and niche integrations are low.

### Score tiers

Absolute, never relative to the night.

| Tier | What it is |
| --- | --- |
| 90-100 | Frontier or open-weight releases you can run today, landmark results. A handful a month. |
| 80-89 | Real technical substance, usable today, from anyone. |
| 70-79 | Useful but narrow, or well made with modest novelty. |
| 55-69 | Minor tools, incremental product news, competent commentary, demos. |
| 35-54 | Unverified solo projects, marketing pages, big numbers with no method, careers and business strategy. |
| 15-34 | Slop, SEO bait, advocacy, manifestos, content-free. |
| 1-14 | Out of scope only. In-scope never goes below 15. |

- **97** "Kimi K3: Open Frontier Intelligence" [kimi.com]: open 3T-class weights, downloadable.
- **85** "The context tax: your coding agent reads the same 600 lines 400 times" [Sonar]: measured across 40 sessions, method stated, applies to any stack, even though it pitches the author's product.
- **74** "Running Gemma 4 26B at 5 tokens/sec on a 13-year-old Xeon" [HN]: exact flags, reproducible, narrow. Small real releases from established creators and papers that report results without showing why also land here.
- **62** "llama.cpp adds a --cache-reuse flag" [HN]: merged, but a knob most builders never touch.
- **45** "SigMap cuts prompt count by 49% across 90 coding tasks" [HN, 3 points]: landing page, big numbers, no method or repo.

### Reading the item

- `source` is where we found the link, not who wrote it. The creator's own site, blog, docs, x.com, `huggingface.co/<creator>` or `github.com/<creator>` is from the creator.
- **Release from the creator** (model, API, tool or capability on the creator's URL): score on reach, never below 70. Not a release, 55-69 as product news:
  - case studies, event recaps, marketing pages
  - a feature inside one vendor's platform only its customers can use, unless it shows a mechanism or measurements usable elsewhere
  - consumer app features with no API, weights or code, even from a lab
  - The floor doesn't hold for a second copy of a launch the feed already has. That's a duplicate, rejected.
- Out of scope (1-14) or release from the creator (70+): pick one rule. A score between fits neither.
- **Repost** of someone else's announcement: about 10 below the release, never above 80; about 20 below if it only restates it. Testing, benchmarking or building with the thing is not a repost.
- **Write-up with a mechanism or measurements from running something real**, applicable on another stack: 80+, on any blog, even if it pitches a product. The most under-scored kind.
- **Paper** showing why something works or fails, enough to change how you build: 78+. Only reporting a good score: 70-79.
- **Explainer** laying out a real builder decision with trade-offs and when each choice is wrong: 70+, no code needed. Advice with nothing to weigh is commentary.
- **Security piece** teaching a method, attack or defence, incident reports included: judged like any write-up. Only reporting an incident happened: 55 max.
- **Paywalled post** (text sets up a result and stops, often under 1000 characters from a usually long publisher): judge only the readable part, since readers hit the same wall. If it stands on its own, score normally. If the claim is behind the wall, cap 55 and say so. Don't `web_fetch` it. Judge per post, never against the publisher.
- **Availability or pricing notice** (existing thing on a new platform, price cut, new region or quota): cap 55. A new launch is a release however short.
- **Proposed spec or protocol** with no users beyond its author: cap 70.
- **AI for science and robotics**: in scope, cap 70 unless there are weights, code or a reproducible method.
- **For founders or leads**: same evidence bar. Data with a method or steps: 55-79. Argument alone: cap 40.

### Lean toward approving

- someone else's working code: repos with docs, skills, harnesses
- practitioner write-ups with measurements that transfer
- papers that show why, not just that it scored well
- model launches, open or API, including a newsletter's report of one
- benchmark and eval work
- AI tooling in any stack, browser and JS included
- Claude Code tooling: configs, skills, token work
- AI security, including incident reports
- individual writers, any audience size

### Reject even when they read well

- cloud vendor how-tos that are console steps for their service
- an aggregator's tutorial or reimplementation of someone else's work
- docs, help centres, dashboards, pricing, "our stack" pages
- availability and pricing notices
- funding, policy, lawsuits, corporate drama

### Tie-breaks

- Topic is never a bonus. Local inference, quantization, privacy, on-device and token cost are common, not merit.
- Approval rate, after the tier is chosen, never moving tiers: +3 for mostly approvals (5+ decisions, 3 in 4 approved), -3 for mostly rejections (5+, 1 in 4 or fewer), else 0.
- Traction is reach evidence only. Single-digit points and no comments: 45 max, 35 for Show-HN-style self-promotion. Strong numbers never lift a thin item past 70.
- Empty snippet and unfetchable page: judging a title alone, cap 70.
- Use the whole range. If four of five are above 85, you stopped discriminating.

### Publisher count

From `find_similar` and `find_duplicates`. Reach evidence only, never lifts thin evidence.

- 3+ publishers and no original in the feed or queue: approve the creator's own item, or the closest to it, and reject the copies as reposts. With nothing from the creator, approve the copy with most substance and say it replaces the release.
- Feed already has the story: every copy is a repost, unless it adds its own testing, benchmarking or building.
- A count of one is not a mark against an article.

### Daily caps

At the end, over the whole night:

- At most two Claude Code items. Approve the two strongest, reject the rest: `"Third-best Claude Code item tonight; daily cap of 2."`

## Verdicts

- **`reason`:** one sentence naming what decided it: the scope rule, the evidence shown or missing, the reach, or the cap. "Landing page with a 49% claim, no method and no repo", not "Low quality". These become labelled data.
- **`summary`:** from the article, not the title. A hook line, then short bullets: what it shows, numbers with their method, what a reader would do with it. No marketing adjectives, no "this article discusses".
- **`kind`, `tags`:** from `list_labels()`, based on the article. Kind: `repo`, `paper`, `model`, or `post` for everything else; github, huggingface and arxiv URLs set their own. Up to 3 tags, only where the tag fits the subject. No tag beats a wrong one. Lab tags (`anthropic`, `openai`, `google`, `meta`, `microsoft`, `nvidia`, `xai`, `qwen`, `deepseek`, `kimi`, `glm`, `mistral`) come on top when the subject is that lab's model or product, not a passing mention. An unknown kind is refused and the candidate stays pending.
- **`publisher_kind`, `publisher_name`:** only when `publisher_kind` is `unknown`. Set once, later articles inherit it.
  - `lab`: trains and releases its own models
  - `company`: sells a product or service, this is its blog or docs
  - `individual`: one person under their own name, including solo projects
  - `media`: covers others' work: newsletters, news sites, multi-writer publications
  - `publisher_name` only when the host doesn't read well: "Dan Luu" for `danluu.com`. Not needed on rejects.

## Finish

Don't stop partway.

Before the report, check these each had their search or check, do any missing, and re-score if it moves:

- every approval from a "new" publisher
- every repost at 55+ whose release neither `find_duplicates` nor `find_similar` showed
- every approval at 75+ resting on a repo, model or paper

Report: approved and rejected counts, web searches, fetches and `check_repo` calls, and blockers.

Don't edit files or commit. If `list_candidates` is missing or says "Authorization failed", stop and say so.
