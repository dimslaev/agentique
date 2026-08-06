// Primary judge. Replaced gpt-oss-120b on 2026-08-06: NVIDIA NIM latency blew
// out under load (single ScoreArticles calls took 52-285s, against ~13s earlier
// the same morning), which serialised into hours of wall-clock because
// score_articles runs its batches strictly in sequence.
client<llm> Haiku {
  provider anthropic
  options {
    api_key env.ANTHROPIC_API_KEY
    model "claude-haiku-4-5-20251001"
    max_tokens 4096
    timeout 120
  }
}

// Was the primary judge: highest-quality of the three below, but times out
// under load, so it gets a generous timeout and falls back to Ministral.
client<llm> GptOss {
  provider openai-generic
  options {
    base_url "https://integrate.api.nvidia.com/v1"
    api_key env.NVIDIA_NIM_API_KEY
    model "openai/gpt-oss-120b"
    timeout 120
  }
}

// Fallback: fast and reliable, lower quality. Used when gpt-oss fails
// (e.g. sustained timeouts under load).
client<llm> Ministral {
  provider openai-generic
  options {
    base_url "https://api.infomaniak.com/2/ai/7/openai/v1"
    api_key env.IK_AI_KEY
    model "mistralai/Ministral-3-14B-Instruct-2512"
    timeout 120
  }
}

// Third fallback: Google Gemini Flash. Cheap, fast, different provider
// than the NVIDIA-backed pair above, so it survives an NVIDIA outage too.
client<llm> Gemini {
  provider google-ai
  options {
    api_key env.GOOGLE_API_KEY
    model "gemini-2.5-flash"
  }
}

// The name every function already references. Now a fallback wrapper: try
// Haiku first, then gpt-oss, then Ministral, with Gemini as last resort.
// Renaming would mean editing all 12 `client Nvidia` sites for no gain, so
// the name stays despite no longer leading with an NVIDIA-backed model.
//
// Order matters most for ScoreArticles: Ministral-3-14B judged with ±15
// run-to-run variance on identical input and intermittently returned fewer
// results than it was given, which the scorer reads as score 0. It stays last
// of the judges for that reason; see plans/scoring-recalibration.md.
client<llm> Nvidia {
  provider fallback
  options {
    strategy [Haiku, GptOss, Ministral, Gemini]
  }
}
