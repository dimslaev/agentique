"""Jev: OpenRouter's structured-decision endpoint.

One ``state`` per request, any number of questions about it. Each question is
evaluated independently and costs only its own tokens, so adding a question to
a request that is being made anyway is nearly free.

The route is alpha and absent from ``GET /api/v1/models``; that listing does
not mean the model is gone.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "~typesafe/jev-latest"
TIMEOUT_SECS = 30.0

# Same shape as the Burst policy in baml_src/clients.baml: a 429 from a
# concurrency cap clears in seconds, so waiting beats failing the link.
BACKOFF_START_SECS = 0.5
BACKOFF_MAX_SECS = 8.0


class JevError(RuntimeError):
    pass


@dataclass(frozen=True)
class Reply:
    answers: dict[str, Any]
    cost: float


def noul(
    instructions: str, true_desc: str | None = None, false_desc: str | None = None
) -> dict:
    """A yes/no question answered as a probability."""
    q: dict = {"type": "noul", "instructions": instructions}
    if true_desc is not None or false_desc is not None:
        q["criteria"] = {"true": true_desc or "", "false": false_desc or ""}
    return q


def score(instructions: str, levels: list[str]) -> dict:
    """An ordinal question over 2-10 described levels, lowest first."""
    if not 2 <= len(levels) <= 10:
        raise ValueError("score takes 2-10 levels")
    return {"type": "score", "instructions": instructions, "criteria": levels}


def choice(instructions: str, options: dict[str, str]) -> dict:
    """Pick one of ``options``, each described by its value."""
    return {"type": "choice", "instructions": instructions, "criteria": options}


def _post(payload: dict) -> httpx.Response:
    return httpx.post(
        URL,
        json=payload,
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        timeout=TIMEOUT_SECS,
    )


def _sleep(secs: float) -> None:
    time.sleep(secs)


def _retry_after(resp: httpx.Response, attempt: int) -> float:
    header = resp.headers.get("retry-after")
    if header:
        try:
            return max(float(header), 0.0)
        except ValueError:
            pass  # an HTTP-date; fall back to our own backoff
    return min(BACKOFF_START_SECS * 2**attempt, BACKOFF_MAX_SECS)


def _unwrap(value: Any, qtype: str) -> Any:
    """An answer arrives either bare or keyed by its question type."""
    if isinstance(value, dict):
        for key in (qtype, "value", "answer"):
            if key in value:
                return value[key]
        return None
    return value


def _answers(body: dict, questions: dict) -> dict[str, Any]:
    raw = body.get("answers")
    if not isinstance(raw, dict):
        raise JevError(f"no answers in response: {str(body)[:200]}")
    answers = {qid: _unwrap(raw.get(qid), q["type"]) for qid, q in questions.items()}
    # A missing answer read as 0 would look like "not a sponsor" or "off topic"
    # and silently decide the link. Better to fail the link loudly.
    missing = [qid for qid, a in answers.items() if a is None]
    if missing:
        raise JevError(f"unanswered: {', '.join(missing)}")
    return answers


def ask(state: Any, questions: dict, *, retries: int = 4) -> Reply:
    """POST once, retry 429 honouring retry-after, raise on a missing answer."""
    payload = {"model": MODEL, "state": state, "questions": questions}
    for attempt in range(retries + 1):
        resp = _post(payload)
        if resp.status_code == 429 and attempt < retries:
            _sleep(_retry_after(resp, attempt))
            continue
        resp.raise_for_status()
        body = resp.json()
        cost = float((body.get("usage") or {}).get("cost") or 0.0)
        return Reply(answers=_answers(body, questions), cost=cost)
    raise AssertionError("unreachable")
