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

// First in the Nvidia wrapper below since 2026-09-13. Second in line from 2026-09-03, replacing
// NVIDIA's gpt-oss-120b, which reached end of life that morning and answered
// every call with 410 Gone - dead weight for hours before anyone noticed,
// because a fallback only speaks up when the primary fails.
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
// max_tokens to be safe.
client<llm> Nemotron {
  provider openai-generic
  retry_policy Burst
  options {
    base_url env.NVIDIA_NIM_BASE_URL
    api_key env.NVIDIA_NIM_API_KEY
    model "nvidia/nemotron-3-super-120b-a12b"
    // The timeout lives in `http`, which BAML applies itself. A bare `timeout`
    // option is sent as a body param, and NIM answers that with 400
    // "Unsupported parameter(s)": every call here failed that way from
    // 2026-09-04 until this block replaced it.
    http {
      request_timeout_ms 120000
    }
  }
}

// Second in the Nvidia fallback. The smaller sibling of the gpt-oss-120b that
// led scoring until its endpoint reached end of life. Measured on the old
// scoring prompt (2026-09-13): clean JSON, but it read a rubric floor as a cap.
client<llm> GptOss20b {
  provider openai-generic
  retry_policy Burst
  options {
    base_url env.NVIDIA_NIM_BASE_URL
    api_key env.NVIDIA_NIM_API_KEY
    model "openai/gpt-oss-20b"
    http {
      request_timeout_ms 120000
    }
  }
}

// Last in the Nvidia fallback since 2026-09-13; primary from 2026-08-06 until
// then. Fast (2-3s) and reliable, but a lower-quality judge: ±15 run-to-run
// variance on identical scoring input, and it intermittently returned fewer
// results than it was given. It stays as
// the last resort because it is the only client not on NIM: when NIM refuses a
// burst, the two clients above it fail together.
client<llm> Ministral {
  provider openai-generic
  retry_policy Burst
  options {
    base_url env.MISTRAL_AI_BASE_URL
    api_key env.MISTRAL_AI_KEY
    model "mistralai/Ministral-3-14B-Instruct-2512"
    // A real client-side timeout. The old `timeout 120` went out as a body
    // param, which this endpoint silently ignored: it never timed anything out.
    http {
      request_timeout_ms 120000
    }
  }
}

// The name every function references. A fallback wrapper: Nemotron first, then
// gpt-oss-20b, then Ministral. The name stays - with two NIM models in front it
// is mostly true.
//
// A Gemini Flash client sat third here until 2026-09-03, when the run that
// needed it got 400 FAILED_PRECONDITION "User location is not supported for
// the API use" - the Google AI API does not serve the prod VPS's region, so
// the last resort had never been able to answer. Removed rather than left in
// place: a client that always fails is not a fallback, it just hides how thin
// the chain really is. A replacement has to be reachable from the box.
client<llm> Nvidia {
  provider fallback
  options {
    strategy [Nemotron, GptOss20b, Ministral]
  }
}
