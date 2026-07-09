#!/usr/bin/env python3
"""Compare NVIDIA NIM models on the article-scoring task.

Plain OpenAI-compatible HTTP calls -- no BAML. Reproduces the ScoreArticles
prompt from baml_src/score.baml and the pipeline's batch-of-5 call pattern,
then scores each candidate model against the gpt-oss-120b baseline stored in
articles.json.

Usage:
    export NVIDIA_NIM_API_KEY=nvapi-...
    python bakeoff.py                      # all candidates
    python bakeoff.py --models a,b         # subset
    python bakeoff.py --list-models        # what the account can actually reach
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

HERE = Path(__file__).parent
BACKOFF_5XX = 8.0  # seconds, doubled per attempt

# Latency notes are the user's own measurements, kept as a triage hint.
CANDIDATES = [
    "openai/gpt-oss-120b",                      # 6.0s  - incumbent, times out under load
    "qwen/qwen3-next-80b-a3b-instruct",         # ---   - current fallback, poor at scoring
    "nvidia/nemotron-3-nano-30b-a3b",           # 1.6s
    "minimaxai/minimax-m2.7",                   # 2.0s  (was m2.5, renamed)
    "moonshotai/kimi-k2.6",                     # 2.0s  (was kimi-k2-instruct-0905 / k2.5, both renamed)
    "mistralai/ministral-14b-instruct-2512",    # 3.5s
    "z-ai/glm-5.2",                             # 4.0s  (was glm5; glm4.7 gone, only z-ai model left)
    "mistralai/mistral-large-3-675b-instruct-2512", # 4.3s (was mistral-large-3-675b, now instruct-2512)
    "nvidia/nvidia-nemotron-nano-9b-v2",        # 8.0s  - overthinks
]

# Gemini speaks OpenAI-compatible on /v1beta/openai/, so the same request shape
# and parser work. Model ids differ entirely from NIM -- verify with
# --list-models before trusting this list.
GOOGLE_CANDIDATES = [
    "gemini-3.5-flash",       # newest flash tier
    "gemini-3.1-flash-lite",  # no 3.5 lite exists; 3.1 is the newest lite
    "gemini-2.5-flash",       # older flash, cost/latency floor comparator
]

PROVIDERS = {
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "env": "NVIDIA_NIM_API_KEY",
        "candidates": CANDIDATES,
        # 2048 is plenty: NIM candidates emit the array directly.
        "extra": {"max_tokens": 2048},
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env": "GOOGLE_API_KEY",
        "candidates": GOOGLE_CANDIDATES,
        # Gemini flash tiers think by default and reasoning tokens count against
        # max_tokens, so a 2048 cap can starve the answer and return empty
        # content. Give headroom and turn thinking off.
        "extra": {"max_tokens": 8192, "reasoning_effort": "none"},
    },
}

SYSTEM = (
    "You are a senior editorial analyst at a developer news platform. Your job is to "
    "evaluate articles for relevance and actionability for AI builders. You are precise, "
    "consistent, and ruthless about filtering noise."
)

# Verbatim from baml_src/score.baml, minus the {{ ctx.output_format }} line.
RUBRIC = """Score every article for developer-actionability on a 1-100 scale.

STEP 1 - SCOPE CHECK (apply first, before scoring):
Is the article about AI, ML, LLMs, foundation models, or AI-adjacent developer tools/infrastructure?
- NO -> score 1-20 and move on. Do NOT apply the scoring guide below.
- Out-of-scope examples: text editors, parsers, version control tools, data structures (CRDTs, B-trees), memory management, general programming tutorials, non-AI open source projects, codebase audits, legacy code. These are general software engineering - not AI.

STEP 2 - SCORE (only for in-scope articles):
Audience: developers, startup founders, and tech leaders building with AI who want to ship faster.

Score 91-100 is reserved for exceptional articles that are BOTH immediately actionable today AND fit one of these themes: local/on-device inference, privacy-preserving AI, efficiency breakthroughs (quantization, token optimization, running models on less hardware), or deep technical dives that explain how something actually works. A score in this range means "a developer could open a terminal and act on this within the hour, AND it reveals a non-obvious insight or technique." Zero is a valid outcome - do not give 91+ just because something is the best of a weak batch.

Models (new releases, benchmarks, evals, model cards, comparisons):
- 81-90: New model release or major update, model system cards, open-weight models a developer can run today
- 71-80: Meaningful benchmark or eval, model comparison with actionable conclusions

Dev (SDKs, frameworks, CLI tools, IDE integrations, open-source projects, tutorials, deployment):
- 81-90: New AI API or SDK, open-source AI tool/library a developer can use today
- 71-80: Fine-tuning guide, RAG pattern, significant framework update, AI infrastructure (training, inference, memory optimization), deployment recipes

Research (papers, breakthroughs, novel techniques):
- 71-80: Research with immediate practical implications, AI security research
- 51-60: Research with near-term practical implications

Industry (funding, platform changes, acquisitions, partnerships, market shifts):
- 51-60: Industry analysis with actionable takeaways, AI platform partnerships
- 31-40: Funding rounds without product details, opinion/commentary with no actionable steps, "AI is changing everything" think pieces, personal anecdotes about using AI

Upgrade to 91-100: if an article would score 81-90 AND fits the top-tier criteria above (local inference, privacy-preserving, efficiency breakthrough, or deep how-it-works dive), give it 91-100.

Bottom tier:
- 1-20: Non-AI topics (see step 1), regulation, politics, lawsuits, corporate drama

Trust bonus: entries may include a [trust: high/medium/low] tag. Give +1 to high-trust sources when content quality is comparable."""

OUTPUT_CONTRACT = """Respond with ONLY a JSON array, no prose and no markdown fences. One object per article, in the same order, each with exactly these keys:
  "url":   the article's url, copied verbatim
  "score": integer 1-100

Example: [{"url": "https://a.com", "score": 84}, {"url": "https://b.com", "score": 12}]"""


def render_batch(articles: list[dict]) -> str:
    lines = [RUBRIC, "", "Articles:"]
    for i, a in enumerate(articles, 1):
        trust = f" [trust: {a['trust']}]" if a.get("trust") else ""
        lines.append(f"{i}. [{a['source']}] \"{a['title']}\" - {a['url']}{trust}")
        if a.get("snippet"):
            lines.append(f"   {a['snippet']}")
    lines += ["", OUTPUT_CONTRACT]
    return "\n".join(lines)


# ── response parsing ────────────────────────────────────────────────────────

THINK = re.compile(r"<think>.*?</think>|<thinking>.*?</thinking>", re.S | re.I)
FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def extract_json_array(text: str) -> list[dict]:
    """Pull the first balanced JSON array out of a model response.

    Handles reasoning models that emit <think> blocks, models that wrap output
    in markdown fences, and models that prepend prose despite instructions.
    """
    text = THINK.sub("", text or "").strip()
    if m := FENCE.search(text):
        text = m.group(1).strip()

    start = text.find("[")
    if start == -1:
        raise ValueError(f"no JSON array in response: {text[:200]!r}")

    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError(f"unbalanced JSON array: {text[:200]!r}")


def content_of(payload: dict) -> str:
    """gpt-oss and other reasoners may put the answer in reasoning_content."""
    msg = payload["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning_content") or ""


# ── model invocation ────────────────────────────────────────────────────────


@dataclass
class BatchResult:
    scores: dict[str, int] = field(default_factory=dict)
    latency: float = 0.0
    error: str | None = None


def score_batch(
    client: httpx.Client,
    model: str,
    batch: list[dict],
    *,
    retries: int = 2,
    extra: dict | None = None,
) -> BatchResult:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": render_batch(batch)},
        ],
        "temperature": 0,
        **(extra or {}),
    }

    last = "unknown"
    for attempt in range(retries + 1):
        t0 = time.monotonic()
        try:
            r = client.post("/chat/completions", json=body)
            elapsed = time.monotonic() - t0
            if r.status_code == 404:
                return BatchResult(error="model_not_available", latency=elapsed)
            if r.status_code == 429 or r.status_code >= 500:
                # 503 "high demand" on Gemini flash tiers is transient and needs
                # real backoff, not the 2s the generic path gives it.
                last = "rate_limited" if r.status_code == 429 else f"http_{r.status_code}"
                if attempt < retries:
                    time.sleep(BACKOFF_5XX * (2**attempt))
                continue
            r.raise_for_status()
            rows = extract_json_array(content_of(r.json()))
            scores = {
                str(row["url"]): max(1, min(100, int(row["score"])))
                for row in rows
                if "url" in row and "score" in row
            }
            return BatchResult(scores=scores, latency=elapsed)
        except httpx.TimeoutException:
            last = "timeout"
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:160].replace("\n", " ")
            last = f"http_{e.response.status_code}: {detail}"
            if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                return BatchResult(error=last, latency=elapsed)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            last = f"parse_error: {e}"
        if attempt < retries:
            time.sleep(2 * (attempt + 1))

    return BatchResult(error=last, latency=time.monotonic() - t0)


# ── metrics ─────────────────────────────────────────────────────────────────


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation with average ranks for ties. None if a side is constant."""
    if len(xs) < 3:
        return None

    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy) ** 0.5


def pct(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile. Guards the small-n case where a naive
    int(n*q)-1 index underflows and returns the minimum instead."""
    if not values:
        return None
    s = sorted(values)
    i = math.ceil(q * len(s)) - 1
    return s[min(max(i, 0), len(s) - 1)]


def evaluate(model: str, got: dict[str, int], arts: list[dict], threshold: int,
             lat: list[float], errors: list[str]) -> dict:
    db = [a for a in arts if a["origin"] == "db" and a["url"] in got]
    syn = [a for a in arts if a["origin"] == "synthetic" and a["url"] in got]

    base = [a["baseline_score"] for a in db]
    mine = [got[a["url"]] for a in db]

    mae = statistics.fmean(abs(b - m) for b, m in zip(base, mine)) if db else None
    rho = spearman(base, mine) if db else None

    # The decision that actually matters: does it keep what gpt-oss kept and
    # drop the out-of-scope negatives?
    kept_db = sum(1 for a in db if got[a["url"]] >= threshold)
    dropped_syn = sum(1 for a in syn if got[a["url"]] < threshold)
    n_correct, n_total = kept_db + dropped_syn, len(db) + len(syn)

    # Metrics are computed only over articles the model actually returned. If it
    # dropped batches, they describe a subset it may have self-selected, so they
    # are not comparable to a full run. Say so loudly rather than rank on them.
    complete = len(got) == len(arts)

    p50, p95 = pct(lat, 0.5), pct(lat, 0.95)
    return {
        "model": model,
        "complete": complete,
        "coverage": f"{len(got)}/{len(arts)}",
        "missing": len(arts) - len(got),
        "mae_vs_baseline": round(mae, 2) if mae is not None else None,
        "spearman": round(rho, 3) if rho is not None else None,
        "recall_on_kept": f"{kept_db}/{len(db)}" if db else "0/0",
        "scope_check_negatives": f"{dropped_syn}/{len(syn)}" if syn else "0/0",
        "threshold_agreement": round(n_correct / n_total, 3) if n_total else None,
        "latency_p50": round(p50, 2) if p50 is not None else None,
        "latency_p95": round(p95, 2) if p95 is not None else None,
        "latency_total": round(sum(lat), 1),
        "errors": errors,
        "scores": got,
    }


# ── driver ──────────────────────────────────────────────────────────────────


def list_models(client: httpx.Client) -> None:
    r = client.get("/models")
    r.raise_for_status()
    for m in sorted(d["id"] for d in r.json()["data"]):
        print(m)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="comma-separated subset of model ids")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--timeout", type=float, default=90.0, help="per-request read timeout (s)")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--provider", choices=sorted(PROVIDERS), default="nvidia")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    prov = PROVIDERS[args.provider]
    key = os.environ.get(prov["env"])
    if not key:
        print(f"{prov['env']} is not set", file=sys.stderr)
        return 2
    out = args.out or str(HERE / f"results_{args.provider}.json")

    timeout = httpx.Timeout(args.timeout, connect=10.0)
    with httpx.Client(
        base_url=prov["base_url"],
        timeout=timeout,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    ) as client:
        if args.list_models:
            list_models(client)
            return 0

        data = json.loads((HERE / "articles.json").read_text())
        arts, threshold, batch_size = data["articles"], data["score_threshold"], data["batch_size"]
        models = args.models.split(",") if args.models else prov["candidates"]
        batches = [arts[i : i + batch_size] for i in range(0, len(arts), batch_size)]

        results = []
        for model in models:
            print(f"\n=== {model} ===", flush=True)
            got: dict[str, int] = {}
            lat: list[float] = []
            errors: list[str] = []

            for n, batch in enumerate(batches, 1):
                res = score_batch(client, model, batch, retries=args.retries, extra=prov["extra"])
                if res.error:
                    errors.append(f"batch{n}:{res.error}")
                    print(f"  batch {n}/{len(batches)}  FAIL {res.error} ({res.latency:.1f}s)", flush=True)
                    if res.error == "model_not_available":
                        break
                else:
                    got.update(res.scores)
                    lat.append(res.latency)
                    print(f"  batch {n}/{len(batches)}  ok  {len(res.scores)} scores  {res.latency:.1f}s", flush=True)
                time.sleep(1)

            if errors and errors[0].endswith("model_not_available"):
                print("  skipped: not available on this account")
                continue

            row = evaluate(model, got, arts, threshold, lat, errors)
            results.append(row)
            print(
                f"  -> MAE {row['mae_vs_baseline']}  rho {row['spearman']}  "
                f"agree {row['threshold_agreement']}  p50 {row['latency_p50']}s",
                flush=True,
            )

        # Complete runs first: a model that skipped batches has metrics over a
        # subset and must never outrank one that scored every article.
        results.sort(
            key=lambda r: (
                not r["complete"],
                -(r["threshold_agreement"] or 0),
                r["mae_vs_baseline"] or 999,
            )
        )
        Path(out).write_text(json.dumps({"threshold": threshold, "results": results}, indent=2))

        print("\n\n## Results (best first)\n")
        hdr = ["model", "agree", "MAE", "rho", "kept", "negs", "p50", "p95", "cov", "errors"]
        print("| " + " | ".join(hdr) + " |")
        print("|" + "|".join("---" for _ in hdr) + "|")
        for r in results:
            flag = "" if r["complete"] else " ** PARTIAL"
            print(
                f"| `{r['model']}`{flag} | {r['threshold_agreement']} | {r['mae_vs_baseline']} | "
                f"{r['spearman']} | {r['recall_on_kept']} | {r['scope_check_negatives']} | "
                f"{r['latency_p50']}s | {r['latency_p95']}s | {r['coverage']} | "
                f"{len(r['errors'])} |"
            )
        if any(not r["complete"] for r in results):
            print(
                "\n** PARTIAL: model did not score every article. Its metrics cover only the\n"
                "   articles it returned and are NOT comparable to a complete run."
            )
        print(f"\nFull scores written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
