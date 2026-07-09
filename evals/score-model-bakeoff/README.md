# Scoring model bakeoff

Find a NVIDIA NIM model to replace `openai/gpt-oss-120b` for **article scoring only**
(`ScoreArticles` in `baml_src/score.baml`).

- `openai/gpt-oss-120b` — scores well, but times out under pipeline load.
- `qwen/qwen3-next-80b-a3b-instruct` — the current fallback in `clients.baml`, not good at scoring.

This harness makes plain OpenAI-compatible calls against `integrate.api.nvidia.com`.
No BAML: BAML's retry/timeout behaviour is exactly what we're trying to characterise, so it
stays out of the loop.

## Run

```bash
export NVIDIA_NIM_API_KEY=nvapi-...

python bakeoff.py                    # all 12 candidates
python bakeoff.py --models z-ai/glm5,nvidia/llama-3.3-nemotron-super-49b
python bakeoff.py --list-models      # what this account can actually reach
python bakeoff.py --timeout 45       # tighter per-request read timeout
```

Writes `results.json` and prints a ranked markdown table.

Only `httpx` is needed — already a backend dependency, so `uv run` inside `backend/` works.

## What it measures

Each model gets the same prompt as production: the `score.baml` rubric verbatim, articles in
batches of 5, `temperature=0`. `{{ ctx.output_format }}` is replaced by an explicit JSON contract
since there's no BAML to generate one.

| metric | meaning |
| --- | --- |
| `threshold_agreement` | **the metric that matters.** Fraction of articles the model routes the same way gpt-oss did, at `SCORE_THRESHOLD=76`. |
| `recall_on_kept` | how many of the 20 known-good articles it keeps (≥76) |
| `scope_check_negatives` | how many of the 5 out-of-scope articles it drops (<76) |
| `mae_vs_baseline` | mean absolute score distance from the gpt-oss baseline |
| `spearman` | rank correlation with the baseline — do relative orderings survive? |
| `latency_p50` / `p95` | per-batch wall time, the reason we're doing this |
| `coverage` | articles the model actually returned a score for |

A model that scores everything 50 gets `scope_check_negatives = 5/5` for free, so read
`threshold_agreement` and `spearman` together — that model lands at `0.2` agreement and `null` rho.

## The dataset

`articles.json` — 25 articles.

**20 `origin: "db"`** — pulled from `.ignored/agentique-new.sql`, `article` table, joined to
`publisher` for `name`/`trust`, snippet = `content[:200]`. Same shape `_to_baml_input()` builds in
`backend/pipeline/run.py`. Stratified across the score range: 4 each from 76–80, 81–85, 86–90,
91–95, 96–100. `baseline_score` is what gpt-oss-120b gave them in production.

**5 `origin: "synthetic"`** — hand-written negatives (CRDTs, ripgrep internals, an AI Act fine, a
funding round, an "AI changes everything" think piece). These exercise the STEP 1 scope check.
`baseline_score` is `null`; the label is `expect: "drop"`.

### Why the negatives are synthetic

The pipeline drops sub-threshold articles before insert (`run.py:326`), so **every row in the
`article` table scored ≥76**. There are no real negatives to sample. `scored_url` records every URL
the pipeline ever evaluated, but stores no score, title, or content — the rejects aren't
recoverable from the dump.

So: this harness tests *"does the model agree with gpt-oss on articles gpt-oss liked"* and
*"does it reject obvious junk"*. It does **not** test the borderline band (a real article that
gpt-oss scored 70) — that data doesn't exist. Treat a high `threshold_agreement` as necessary but
not sufficient; shadow-run the winner before switching `clients.baml`.

## Candidates

From observed latency on this account (fastest first):

| model | observed | note |
| --- | --- | --- |
| `nvidia/nemotron-3-nano-30b-a3b` | 1.6s | speed king |
| `minimaxai/minimax-m2.5` | 2.0s | |
| `moonshotai/kimi-k2-instruct-0905` | 2.0s | much faster than k2.5 |
| `mistralai/ministral-14b-instruct-2512` | 3.5s | |
| `z-ai/glm5` | 4.0s | |
| `nvidia/llama-3.3-nemotron-super-49b` | 4.0s | good power/speed balance |
| `mistralai/mistral-large-3-675b` | 4.3s | fast for its size |
| `openai/gpt-oss-120b` | 6.0s | **incumbent** |
| `nvidia/nvidia-nemotron-nano-9b-v2` | 8.0s | overthinks |
| `moonshotai/kimi-k2.5` | 30s | |
| `z-ai/glm4.7` | 32s | |

Excluded as too slow to be worth scoring: `deepseek-ai/deepseek-v3.2` (~2m),
`meta/llama-3.1-405b-instruct` (10–50s, unstable).

## Reliability

- 90s read timeout, 10s connect (`--timeout` to change).
- 2 retries on timeout / 429 / 5xx / unparseable output, backing off.
- 429 sleeps 3s × attempt.
- A 404 marks the model unavailable and skips it — model IDs drift on NIM, check `--list-models`.
- Responses are parsed leniently: `<think>` blocks stripped, markdown fences unwrapped, first
  balanced JSON array extracted. `reasoning_content` is read when `content` is empty (gpt-oss).
- Every failure lands in `errors[]` rather than killing the run.
