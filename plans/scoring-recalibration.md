# Scoring recalibration — July 2026

Manual rescore of every article published in the last 31 days that the pipeline
scored ≥ 90 (128 of 331). Purpose: find why junk clears 90 and retune the prompt.

## What the pipeline produced

Distribution of the 331 stored articles (threshold is 76, so nothing below that
exists):

| score | count |
|---|---|
| 95 | 53 |
| 93 | 28 |
| 92 | 25 |
| 85 | 68 |
| 87 | 17 |
| 78 | 51 |
| rest | spread thin |

Three round numbers hold 40% of the corpus. The scorer is not ranking, it is
bucketing.

## Failure modes found

1. **Theme keywords are a jackpot.** The old prompt promised 91-100 to anything
   about local inference, privacy, quantization or token cost. Result: a
   campaign landing page ("Protect your right to run local AI", no code, no
   claim, nothing to do) scored 95 — the same as Kimi K3, an open 3T frontier
   model. The scorer matched keywords, not substance.

2. **No credibility axis.** An unknown solo dev's weekend repo and a lab release
   land in the same band. `SP/1.0: deterministic verdicts for AI-agent
   decisions` (unheard-of author, spec with no adoption) = 95. `Gemini 3.6 Flash`
   = 95. GPT-5.6 GA = 92, i.e. *below* both.

3. **Empty content still scores high.** Nine of the 95s have no summary at all —
   the fetch failed and the scorer judged the title alone. The article the
   complaint named, `Why OpenAI's GPT-2 Weights Outperform Custom Models After
   Fixing Bug` (93), is one of them: a part-N personal learn-by-building series,
   scored blind off a title that pattern-matches "deep technical dive".

4. **Tweet reposts and marketing pages are treated as articles.** The single 100
   is an x.com post about a NEAR crypto swap API — not AI at all, and it beat
   every real release this month. `Aligned News` (an x.com repost feed) holds 4
   of the top 5.

5. **Newsletter/SEO slop is indistinguishable from engineering writing.** Three
   parts of the same "$0 Hermes agent on a free VM" Substack series each scored
   93-95. "Turn Claude Opus 5 Into a Financial Analyst That Never Sleeps" = 95.

6. **Unverified numbers are rewarded, not discounted.** "SigMap cuts prompt count
   49%, tokens 97%" (landing page, no repo, no method) = 94.

7. **The rubric's own bands make the 76 threshold a no-op.** Every in-scope
   article maps to 71-95 in the old guide, so the cutoff rejects almost nothing.

## New scale

Absolute, not batch-relative. Median in-scope article sits around 55.

| band | meaning |
|---|---|
| 90-100 | frontier release or landmark result: verified, broadly consequential, usable now |
| 80-89 | real technical substance from a credible source, actionable today |
| 70-79 | useful but narrow, or good writing with modest novelty |
| 55-69 | minor tools, incremental news, decent commentary |
| 35-54 | unverified solo projects, thin newsletter posts, marketing |
| 15-34 | slop, SEO bait, tweet reposts, content-free |
| 1-14 | out of scope |

Two axes decide the band: **evidence** (numbers, code, reproducibility) and
**consequence** (how many builders it affects). Theme is no longer a bonus.

## Biggest corrections (pipeline → mine)

| id | pipeline | mine | article |
|---|---|---|---|
| 1124 | 100 | 12 | NEAR confidential swap API (crypto, x.com) |
| 1070 | 99 | 35 | "30-minute AI agent" Substack, Gemma 2 + Docker |
| 1107 | 98 | 40 | image-token-compression trick, unverified tweet |
| 1004 | 95 | 25 | "The Model Is the Brain, Everything Else Is the Desk" |
| 1014 | 95 | 30 | "Protect your right to run local AI" campaign page |
| 1047 | 95 | 30 | "Superpowers 6.0: tokens down 60%" |
| 1169 | 95 | 25 | "$0 cloud VM for your Hermes agent (Part 1)" |
| 1297 | 95 | 22 | same series, Part 2 |
| 1093 | 93 | 25 | same series, third post |
| 1295 | 95 | 25 | SP/1.0 spec, unknown author |
| 1331 | 95 | 25 | "Claude Opus 5 as a financial analyst that never sleeps" |
| 1246 | 91 | 20 | "Why Human Language is the New Code" |
| 1197 | 95 | 30 | Rust crypto verification in SymCrypt (not AI) |
| 1343 | 92 | 40 | tree-based models for tabular ML (not AI-builder) |
| 1021 | 94 | 35 | SigMap, 97% token cut, landing page only |
| 1349 | 93 | 45 | GPT-2 weights bugfix, part-N personal series, no content fetched |
| 1094 | 92 | 12 | broken title with leaked JSON, event-promo tweet |

Under-scored by the old prompt:

| id | pipeline | mine | article |
|---|---|---|---|
| 1218 | 95 | 97 | Kimi K3, open 3T-class frontier model |
| 1088 | 92 | 92 | GPT-5.6 family GA (correct, but ranked below slop) |
| 1185 | 95 | 88 | Leanstral 1.5, Apache-2.0, 587/672 PutnamBench |
| 1251 | 95 | 88 | Gemini 3.6 Flash / 3.5 Flash-Lite |
| 1071 | 96 | 88 | vLLM native transformers backend |
| 933 | 93 | 85 | TurboPrefill, 2.7× faster prefill, upstream llama.cpp PR |
| 1101 | 95 | 85 | Flash-MSA sparse-attention training kernels |
| 1225 | 92 | 80 | Netflix in-house LLM serving |
| 1044 | 92 | 80 | RAG context pruned 68% at 96% recall |

Full rescore of all 330 last-month articles: `plans/rescore-2026-07.csv`.

## Applied to prod

All 330 articles published in the 31 days to 2026-07-31 now carry hand-assigned
scores on the scale above — the ≥90 band first (128 rows), then the remaining
202 in a second pass. Two `update article set score` statements, `UPDATE 128`
and `UPDATE 202`. Pre-write snapshots are in the session scratchpad
(`backup_scores.csv`, `backup_all.csv`) if any of it needs reverting.

Distribution before and after:

| band | before | after |
|---|---|---|
| 90-100 | 128 | 22 |
| 80-89 | 105 | 57 |
| 70-79 | 60 | 54 |
| 60-69 | 0 | 55 |
| 50-59 | 0 | 63 |
| 40-49 | 0 | 41 |
| 20-39 | 0 | 36 |

Nothing scored below 76 before, because 76 was the insert threshold — the old
rubric simply had no way to say "this is filler". Two thirds of the month now
sits below 70.

## Validation

Ran the retuned prompt over 20 labelled items spanning the whole range, in
batches of 5, with `Ministral-3-14B` pinned as the judge (no fallback), and
diffed against the manual scores.

- mean |model − manual| = **7.6 to 9.2** across runs, versus 40+ for the old
  prompt on the same 20 (which put all of them in 90-100).
- Ordering is now correct: slop lands 1-45, real engineering 65-97.
- Specific fixes confirmed: NEAR crypto tweet 100 → 5, "$0 cloud VM Part 1"
  95 → 25, "Human Language is the New Code" 91 → 25, SigMap 94 → 30, while
  Kimi K3 holds 97 and the vLLM/Transformers integration holds 88.
- The measured-numbers rule works: "pruned RAG context 68% at 96% recall" moved
  from 55 (early draft over-penalised any percentage) to 80.
- The lab-domain floor fixed GPT-5.6 GA, which swung 45/65/85 across runs before
  it and now sits 72-98.

Two residual issues, both from the judge model rather than the wording:

1. **Run-to-run variance of ±15 on some items.** Same input, same prompt,
   different score. The rubric constrains the band; it cannot make a 14B model
   deterministic.
2. **Ministral silently drops articles from a batch.** In roughly one run in
   three it returned 4 results for 5 inputs, sometimes missing a whole batch.
   `apply_scores` maps a missing URL to score 0, so those articles are discarded
   without a trace — including good ones. Worth a retry-on-short-response in
   `score_articles`, independent of any prompt work.

## Changes made

- `baml_src/score.baml` — rewritten: scope check widened, source-integrity step
  added, theme bonus replaced by evidence × consequence, anti-clustering and
  absolute-scale rules, empty-snippet cap at 70, worked anchor examples drawn
  from the table above, four regression tests.
- `backend/pipeline/heuristics.py` — `SCORE_THRESHOLD` 76 → 65. Required: the
  new scale puts the median in-scope article near 55, so 76 would reject almost
  the entire feed.

## Not changed — needs a decision

`baml_src/clients.baml` runs the fallback as `[Ministral, GptOss, Gemini]`, so
`Ministral-3-14B` is the judge in practice while the comment above it says
gpt-oss-120b is primary. The comment and the code disagree; one of them should
change. Left alone here because the retuned prompt hits mean error under 10 on
Ministral, which is good enough for a 65 threshold — but the ±15 variance and
the dropped-batch behaviour above are both properties of that model.
