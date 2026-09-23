"""The Jev transport's two guarantees: a 429 waits as long as it is told to
and tries again, and an answer set with a hole in it is an error, never a
quiet zero that reads as "not a sponsor" or "off topic".
"""

from __future__ import annotations

import httpx
import pytest

from pipeline import jev

QUESTIONS = {
    "is_sponsor": jev.noul("sponsor?", "yes", "no"),
    "kind": jev.choice("what?", {"article": "a", "product": "p"}),
}


def _resp(status: int, body: dict | None = None, headers: dict | None = None):
    return httpx.Response(
        status,
        json=body or {},
        headers=headers,
        request=httpx.Request("POST", jev.URL),
    )


def _stub(monkeypatch, responses):
    sent: list[dict] = []
    slept: list[float] = []

    def post(payload):
        sent.append(payload)
        return responses.pop(0)

    monkeypatch.setattr(jev, "_post", post)
    monkeypatch.setattr(jev, "_sleep", slept.append)
    return sent, slept


def test_a_429_waits_for_retry_after_then_succeeds(monkeypatch):
    ok = {
        "answers": {"is_sponsor": {"noul": 0.9}, "kind": {"choice": "product"}},
        "usage": {"cost": 0.00002},
    }
    sent, slept = _stub(
        monkeypatch, [_resp(429, headers={"retry-after": "3"}), _resp(200, ok)]
    )

    reply = jev.ask({"link_text": "x"}, QUESTIONS)

    assert slept == [3.0]
    assert len(sent) == 2
    assert reply.answers == {"is_sponsor": 0.9, "kind": "product"}
    assert reply.cost == pytest.approx(0.00002)


def test_the_request_carries_model_state_and_questions(monkeypatch):
    ok = {"answers": {"is_sponsor": 0.1, "kind": "article"}}
    sent, _ = _stub(monkeypatch, [_resp(200, ok)])

    jev.ask({"link_text": "x"}, QUESTIONS)

    assert sent[0] == {
        "model": jev.MODEL,
        "state": {"link_text": "x"},
        "questions": QUESTIONS,
    }


def test_a_429_without_retry_after_backs_off_on_its_own(monkeypatch):
    ok = {"answers": {"is_sponsor": 0.1, "kind": "article"}}
    _, slept = _stub(monkeypatch, [_resp(429), _resp(429), _resp(200, ok)])

    jev.ask({}, QUESTIONS)

    assert slept == [jev.BACKOFF_START_SECS, jev.BACKOFF_START_SECS * 2]


def test_429s_past_the_retry_budget_raise(monkeypatch):
    _stub(monkeypatch, [_resp(429) for _ in range(3)])

    with pytest.raises(httpx.HTTPStatusError):
        jev.ask({}, QUESTIONS, retries=2)


def test_a_missing_answer_raises_instead_of_reading_as_zero(monkeypatch):
    _stub(monkeypatch, [_resp(200, {"answers": {"kind": {"choice": "article"}}})])

    with pytest.raises(jev.JevError, match="is_sponsor"):
        jev.ask({}, QUESTIONS)


def test_a_response_with_no_answers_raises(monkeypatch):
    _stub(monkeypatch, [_resp(200, {"error": "nope"})])

    with pytest.raises(jev.JevError):
        jev.ask({}, QUESTIONS)


def test_a_zero_probability_is_an_answer_not_a_hole(monkeypatch):
    _stub(monkeypatch, [_resp(200, {"answers": {"is_sponsor": 0.0, "kind": "x"}})])

    assert jev.ask({}, QUESTIONS).answers["is_sponsor"] == 0.0


def test_criteria_are_optional_on_a_noul():
    assert "criteria" not in jev.noul("sponsor?")


def test_score_needs_two_to_ten_levels():
    with pytest.raises(ValueError):
        jev.score("how good?", ["only one"])
