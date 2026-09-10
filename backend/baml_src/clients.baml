// The provider caps how many requests may be in flight at once, far below its
// per-minute quota: measured 2026-09-03, 5 parallel calls all answered while 10
// returned 429 in ~90ms with x-ratelimit-remaining still at 1980/2000, and the
// cap refills within ~10s. So a 429 here means "too many at once", never "out
// of budget", and waiting is the correct response. Without this policy those
// bursts fell through to the fallback client instead.
retry_policy Burst {
  max_retries 4
  strategy {
    type exponential_backoff
    delay_ms 500
    multiplier 2
    max_delay_ms 8000
  }
}

// Second in line as of 2026-09-03, replacing NVIDIA's gpt-oss-120b, which
// reached end of life that morning and answered every call with 410 Gone. The
// slot had been dead weight for hours before anyone noticed, because a fallback
// only speaks up when the primary fails.
//
// Still NVIDIA NIM, deliberately: a fallback on Ministral's own provider would
// share its rate limiter, and the failure this slot exists to absorb is
// Mistral refusing a burst. A second provider is the whole point.
//
// Measured 2026-09-03 on a SelectProductLink-shaped prompt: 1.5-6.8s across
// sequential calls, all answering with clean JSON and the right pick — no sign
// of the 52-285s latency that made gpt-oss-120b unusable, though that was a
// property of the endpoint under load, so it is worth re-measuring if runs
// start crawling. Past 8 parallel calls NIM starts returning 503; the retry
// policy covers those.
//
// Qwen3.5-397B was the other candidate and judged just as well,
// but it is a reasoning model: it spends its budget in a `reasoning` field and
// emits an EMPTY content string if it runs out before it stops thinking (427
// completion tokens for a two-element array). That needs a large explicit
// max_tokens to be safe, on top of sharing Ministral's limiter.
client<llm> Nemotron {
  provider openai-generic
  retry_policy Burst
  options {
    base_url env.NVIDIA_NIM_BASE_URL
    api_key env.NVIDIA_NIM_API_KEY
    model "nvidia/nemotron-3-super-120b-a12b"
    timeout 120
  }
}

// Primary as of 2026-08-06: fast and reliable, lower quality. Chosen for
// throughput — it answers in 2-3s where gpt-oss was taking minutes. See the
// variance warning on the Nvidia wrapper below before moving it back.
client<llm> Ministral {
  provider openai-generic
  retry_policy Burst
  options {
    base_url env.MISTRAL_AI_BASE_URL
    api_key env.MISTRAL_AI_KEY
    model "mistralai/Ministral-3-14B-Instruct-2512"
    timeout 120
  }
}

// The name every function already references. A fallback wrapper: try Ministral
// first, drop to Nemotron if it fails. Renaming would mean editing all 12
// `client Nvidia` sites for no gain, so the name stays — and with Nemotron in
// the second slot it is at least half true again.
//
// A Gemini Flash client sat third here until 2026-09-03, when the run that
// needed it got 400 FAILED_PRECONDITION "User location is not supported for
// the API use" - the Google AI API does not serve the prod VPS's region, so
// the last resort had never been able to answer. Removed rather than left in
// place: a client that always fails is not a fallback, it just hides how thin
// the chain really is. A replacement has to be reachable from the box.
//
// KNOWN COST OF THIS ORDER, for ScoreArticles specifically: Ministral-3-14B
// judged with ±15 run-to-run variance on identical input and intermittently
// returned fewer results than it was given, which apply_scores reads as
// score 0 — i.e. a silent reject. gpt-oss-120b led for that reason until its
// provider latency made full runs impossible. Traded accuracy for a run that
// finishes. Nemotron looks like the better judge and is worth trying in front
// for scoring, but that swap needs a full score_articles pass measured end to
// end before it lands. See plans/scoring-recalibration.md.
client<llm> Nvidia {
  provider fallback
  options {
    strategy [Ministral, Nemotron]
  }
}
