# scout-rejects 2026-11-25

- Rejects in the last 30 days: `below_threshold` 2677 (previous 30 days: 2015, +33%) and `thin_repo` 2 (previous: 0). `prefilter`, `duplicate` and `unusable_summary` have 0 rows in either window. No stage meets the stage-bug bar of 20+ rows and 2x growth. The biggest movers: aifeed-dev +116 (240 rejects, average score 18, 1 approval, 0 likes; this belongs to discover-publishers), marktechpost +58 and vercel +43.
- Rows that are not agent verdicts are stored as `below_threshold`. There are 79 of them: 36 from the one-off `backend/scripts/marktechpost_to_links.py` (average score 72, and the reason cites ADR 22, which is about stories) and 43 removed by hand on 2026-11-22 (average about 73). They inflate the stage's average score and mix with the reasons the rubric treats as labelled data. Proposal: `removed-stage`.
- The 43 hand removals led to the rubric edits of 11-21/22 (AI for science, hardware, robotics, interpretability, alignment research, consumer features, single-vendor features, single-industry models). None of them is in `regression.md`, and its Runs table has no run since 09-23, so the new rules shipped untested. Proposal: `regression-nov22-removals`. It also found a broken sentence in the rubric: "A company disclosing its own breach: unless the company is well known impacting thousands of users."
- Rubric blind spot: none met the bar. Six publishers have 5+ rejects averaging 55-64 (marktechpost, aligned-news, simon-willison, nvidia-developer, cobus-greyling, google-ai-blog). I read 18 simon-willison, 9 cobus-greyling, 11 nvidia-developer, 7 google-ai-blog and 6 openai-blog rejects, plus the rejects scored 50-69 since 11-22. They are retellings, second copies of launches, plugin point releases and narrow vendor how-tos, which the rubric rejects on purpose.
- Competitor input: the 4 AI-for-science rejects follow the scope rule. "Install as App" (score 50) is the one disputed reject, but it is a single case, and the labels conflict. A liked lab feature, "Claude Now Works with Google Docs" (74), sits against two lab features removed by hand, "Let Gemini tackle repetitive chores on your Mac" (70) and "Gemini Notebook Turns Sources Into Interactive Sites" (70). I could not write one line that separates them, so there is no diff. The missing AINews links were fixed after the 04:00 run (commit 10f14ef, 2026-11-25 22:12, "read ainews issues and poll ai/tldr"). No query errored or hit 1000 rows.

Ledger:
- removed-stage | Record hand and script removals under their own reject stage, not below_threshold | proposed
- regression-nov22-removals | Add the Nov 22 hand removals and liked look-alikes to regression.md and run the set on the current rubric | proposed

## Details

### removed-stage

- Add `removed = "removed"` to `RejectStage` in `backend/app/core/db/ledger.py`. Use it in `marktechpost_to_links.py` and in whatever path wrote the "Removed by hand" rows. Backfill: `update scored_url set stage='removed' where stage='below_threshold' and (reason ilike 'removed by hand%' or reason like 'aggregator retelling, replaced by the links it covers%')` (79 rows).
- Fix the script's reason so it cites the right ADR. ADR 22 is "stories grouped by reading".
- This gives scouts and anyone building regression sets a clean column of agent verdicts. It also keeps the human overrides as their own label, which is what regression wants.

### regression-nov22-removals

No change to `SKILL.md`. Add these rows to the main table in `regression.md`, then do a run and log it in Runs.

The rows the current rubric must reject (`noise`), one or more per rule added on 11-21/22:

| label | kind | publisher | was | new | article |
|---|---|---|---|---|---|
| noise | post | METR | 84 | - | [AI R&D-relevant model capabilities are improving rapidly](https://metr.org/blog/2026-11-20-q4-2026-capability-update/) |
| noise | post | Microsoft Research | 80 | - | [Misalignment signals in Kimi K3](https://commandline.microsoft.com/misalignment-signals-in-kimi-k3-what-probes-flag-and-where-they-peak/) |
| noise | post | notesbylex.com | 78 | - | [Weight-Space Programming builds neural networks like a 1990s researcher](https://notesbylex.com/weight-space-programming-1990s.html) |
| noise | paper | Apple ML Research | 72 | - | [Depth Pro 2](https://machinelearning.apple.com/research/depth-pro-2-monocular) |
| noise | post | Anthropic | 70 | - | [Claude solves two open problems in the physics of black holes](https://www.anthropic.com/research/claude-black-hole-physics) |
| noise | model | ElevenLabs | 70 | - | [Scribe v3 Live Medical](https://elevenlabs.io/blog/scribe-v3-live-medical) |
| noise | post | Vercel | 71 | - | [Introducing Vercel Board](https://vercel.com/blog/introducing-vercel-board) |
| noise | post | Stripe | 72 | - | [Give your agents controlled access to analyze your data and move funds](https://stripe.com/blog/give-your-agents-controlled-access-to-analyze-your-data-and-move-funds) |
| noise | repo | natsu0529 | 74 | - | [agent-mcts](https://github.com/natsu0529/agent-mcts) |
| noise | post | Sierra | 75 | - | [Releasing Personal Agent Protocol 1.0](https://sierra.ai/blog/releasing-poppy) |
| noise | post | Together AI | 64 | - | [Security event: Prompt leakage, June and July 2026](https://www.together.ai/blog/security-event-prompt-leakage-for-requests-in-june-and-july-of-2026) |

Liked look-alikes the new rules could pull out. These must stay kept:

| label | kind | publisher | was | new | article |
|---|---|---|---|---|---|
| love | post | Claude | 74 | - | [Claude Now Works with Google Docs, Sheets, and Slides](https://claude.com/resources/articles/claude-now-works-in-google-docs-sheets-and-slides) |
| love | post | GitLab | 70 | - | [GitLab Orbit is GA](https://about.gitlab.com/blog/gitlab-orbit-ga/) |
| love | post | Vercel | 79 | - | [durable-harness for agents](https://vercel.com/blog/making-every-harness-durable) |
| love | post | Anthropic | 78 | - | [OSS Scanner by Anthropic](https://red.anthropic.com/oss-scanner/) |
| love | post | Perplexity | 73 | - | [Introducing Hybrid Compute on Mac](https://www.perplexity.ai/hub/blog/introducing-hybrid-compute-on-mac) |

Risk: the consumer-feature and single-vendor-feature rules sit close to the liked rows above. If the run drops 2 or more of them, the 11-22 wording is too broad.

Rubric defect to fix during that run, in "Reading the item" > Security piece:
- before: "A company disclosing its own breach: unless the company is well known impacting thousands of users."
- after (suggested): "A company disclosing its own breach: 55 max, unless the company is well known and thousands of users were affected."
