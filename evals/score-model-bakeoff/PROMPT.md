# Cloud agent prompt

Paste the text below into the cloud agent, replacing `<PASTE-TOKEN-HERE>` with the real
NVIDIA NIM key. **Do not commit the key** — it belongs in the prompt, not in the repo.

---

You are running a model bakeoff on branch `eval/score-model-bakeoff`.

Goal: pick a NVIDIA NIM model to replace `openai/gpt-oss-120b` for article scoring.
gpt-oss scores well but times out under pipeline load; the current fallback
`qwen/qwen3-next-80b-a3b-instruct` is fast but scores poorly.

Setup:

```bash
export NVIDIA_NIM_API_KEY=<PASTE-TOKEN-HERE>
cd evals/score-model-bakeoff
```

Run these steps in order.

**1. Confirm the model IDs resolve.** NIM model IDs drift, and `bakeoff.py`'s candidate list was
written from a latency table, not from the live catalog.

```bash
python bakeoff.py --list-models > /tmp/available.txt
wc -l /tmp/available.txt
```

Cross-check every id in `CANDIDATES` (top of `bakeoff.py`) against `/tmp/available.txt`. For any
that is missing, find the closest live id (same family and size) and fix the list. Note every
substitution you make — a renamed `nemotron-3-nano-30b-a3b` is not the same evidence as the model
we actually measured at 1.6s.

**2. Smoke-test one fast model** before spending the full run:

```bash
python bakeoff.py --models nvidia/nemotron-3-nano-30b-a3b --timeout 60
```

Expect 5 batches × 5 articles, a score for all 25 articles, and a printed table row. If coverage is
below 25/25 or `errors` is non-empty, read the failure before continuing — a systematic parse error
will silently poison every model in the full run.

**3. Full run.** This is the long step; batches are sequential per model with a 1s gap.

```bash
python bakeoff.py --timeout 90 2>&1 | tee run.log
```

**4. Report.** Write your findings to `RESULTS.md` on the branch and commit it. Include:

- The ranked table `bakeoff.py` prints.
- Any model ids you substituted in step 1, and any that 404'd.
- **A recommendation.** The metric that decides it is `threshold_agreement` — the fraction of
  articles routed the same way gpt-oss routed them at `SCORE_THRESHOLD=76`. Break ties on
  `latency_p50`, since latency is the entire reason for this exercise.
- `spearman` as a sanity check. A model can hit high agreement by scoring everything near the
  threshold; if rho is low or `null`, the agreement number is not real. Say so.
- Whether the winner cleared the 5 synthetic negatives (`scope_check_negatives`). A model that
  keeps out-of-scope articles is unusable regardless of its MAE.
- Anything that surprised you: models that returned prose instead of JSON, ignored
  `temperature=0`, clipped at `max_tokens`, or whose latency diverged sharply from the table in
  `README.md`.

Constraints:

- Do not modify `articles.json`. The baseline scores are the ground truth for this comparison.
- Do not change the prompt in `bakeoff.py` (`SYSTEM`, `RUBRIC`, `OUTPUT_CONTRACT`). It is a verbatim
  port of `baml_src/score.baml`; editing it invalidates the comparison against production scores.
- You may edit `CANDIDATES`, and you may pass `--timeout` / `--retries`.
- Do not switch the model in `baml_src/clients.baml`. This branch produces evidence, not a cutover.
- If a model burns more than ~5 minutes of wall time, drop it and note that it was dropped. Slow is
  itself a disqualifying result here.

Read `README.md` first — it explains why the negatives are synthetic and why a high
`threshold_agreement` is necessary but not sufficient.
