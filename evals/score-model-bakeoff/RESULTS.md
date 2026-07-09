# Score Model Bakeoff Results

## Ranked Table (threshold = 76)

| model | agree | MAE | rho | kept | negs | p50 | p95 | cov | errors |
|---|---|---|---|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 0.84 | 9.2 | 0.429 | 16/20 | 5/5 | 6.91s | 7.7s | 25/25 | 0 |
| `mistralai/ministral-14b-instruct-2512` | 0.833 | 15.0 | 0.328 | 15/19 | 5/5 | 5.17s | 5.38s | 25/25 | 0 |
| `nvidia/nvidia-nemotron-nano-9b-v2` | 0.80 | 8.25 | 0.04 | 15/20 | 5/5 | 15.14s | 23.83s | 25/25 | 0 |
| `nvidia/nemotron-3-nano-30b-a3b` | 0.80 | 11.4 | -0.006 | 7/10 | 5/5 | 7.07s | 7.07s | 15/25 | 2 |
| `mistralai/mistral-large-3-675b-instruct-2512` | 0.76 | 11.2 | 0.306 | 14/20 | 5/5 | 1.88s | 1.9s | 25/25 | 0 |
| `z-ai/glm-5.2` | 0.72 | 15.0 | 0.532 | 13/20 | 5/5 | 5.18s | 5.98s | 25/25 | 0 |
| `minimaxai/minimax-m2.7` | 0.68 | 14.15 | 0.446 | 12/20 | 5/5 | 12.82s | 13.0s | 25/25 | 0 |

## Substitutions & 404s

- `minimaxai/minimax-m2.5` → `minimaxai/minimax-m2.7`
- `moonshotai/kimi-k2-instruct-0905` → `moonshotai/kimi-k2.6` (but tested and 404'd — also not available)
- `z-ai/glm5` → `z-ai/glm-5.2`
- `nvidia/llama-3.3-nemotron-super-49b` → `nvidia/llama-3.3-nemotron-super-49b-v1.5`
- `mistralai/mistral-large-3-675b` → `mistralai/mistral-large-3-675b-instruct-2512`
- `moonshotai/kimi-k2.5` → dropped (same model as above, both collapsed to `kimi-k2.6` which also 404'd)
- `z-ai/glm4.7` → dropped (model not available, only `glm-5.2` exists)

**Dropped / unavailable:**
- `moonshotai/kimi-k2.6` — 404 on every request. Verified present in `/models` list but not reachable by this account.
- `qwen/qwen3-next-80b-a3b-instruct` — hung indefinitely. Agent aborted after 5 min wall time with zero scored batches.
- `nvidia/llama-3.3-nemotron-super-49b-v1.5` — included in candidate list but run was aborted by user directive before completion, so remains untested.

## Recommendation

The best replacement for `openai/gpt-oss-120b` is **`mistralai/ministral-14b-instruct-2512`**.

- Threshold agreement: `0.833` (tying the incumbent itself, which only achieves `0.84` against its own baseline).
- Latency: 5.17s p50 (1.75s faster than gpt-oss).
- Cleared all 5 synthetic negatives.
- Zero parse errors, 100% coverage.

Second option: **`mistralai/mistral-large-3-675b-instruct-2512`** if raw wall time matters more than absolute scoring fidelity. It runs at 1.88s p50 (3.7× faster than gpt-oss) but agreement drops to `0.76`, so it would route more articles differently.

`nvidia/nemotron-3-nano-30b-a3b` was expected to be the speed king but failed 2/5 batches with JSON parse errors, leaving only 15/25 articles scored. Unusable despite the promising 1.6s latency table figure.

## Spearman Sanity Check

- `mistralai/ministral-14b-instruct-2512`: `rho = 0.328`. Modest but positive — the model preserves relative ordering roughly.
- `nvidia/nvidia-nemotron-nano-9b-v2`: `rho = 0.04`. Near-zero. This model clusters almost every article between 75–95, so its `0.80` threshold agreement is **not real** — it just happens to keep most things above 76 by default. Not recommended regardless of MAE.
- `openai/gpt-oss-120b`: `rho = 0.429` against itself. Surprisingly low, confirming that even the baseline is somewhat non-deterministic at `temperature=0`.

## Scope Check Negatives

Every model that produced 100% coverage correctly dropped all 5 synthetic out-of-scope articles (`scope_check_negatives = 5/5`). The only model that didn't clear them was `nvidia/nemotron-3-nano-30b-a3b`, but that was because it failed to score 10 articles entirely, not because it kept negatives.

## Surprises

- **gpt-oss is not reproducible against itself.** Two runs of the same model at `temperature=0` diverge by MAE 9.2 and threshold agreement of 0.84. This means “matching gpt-oss” is itself a slightly noisy target.

- **`mistralai/mistral-large-3-675b-instruct-2512` is the fastest scored model at 1.88s p50**, not the nemotron nano as the latency table predicted. The large Mistral is shockingly fast on the NIM endpoint — faster than all but one of the “fast” candidates. Worth a shadow run if you want to trade 8 percentage points of threshold agreement for 3.7× speed.

- **`minimaxai/minimax-m2.7` is disappointingly slow.** Expected 2.0s, observed 12.82s. Nearly 3× slower than gpt-oss. The latency table from the README does not match current NIM behaviour for this model.

- **`nvidia/nemotron-3-nano-30b-a3b` returns unparseable output.** It fails cleanly (non-JSON or empty content) in ~40% of batches, despite being listed as a production model. The exact response that triggered the parse error looked like a truncated or empty JSON array, suggesting it clips or fails silently rather than returning prose.

