// Second in line as of 2026-08-06. Highest-quality judge of the three, but
// NVIDIA NIM latency made it unusable under load: single ScoreArticles calls
// took 52-285s against ~13s earlier the same morning, and score_articles runs
// its batches in sequence, so a full run stopped finishing.
client<llm> GptOss {
  provider openai-generic
  options {
    base_url "https://integrate.api.nvidia.com/v1"
    api_key env.NVIDIA_NIM_API_KEY
    model "openai/gpt-oss-120b"
    timeout 120
  }
}

// Primary as of 2026-08-06: fast and reliable, lower quality. Chosen for
// throughput — it answers in 2-3s where gpt-oss was taking minutes. See the
// variance warning on the Nvidia wrapper below before moving it back.
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

// The name every function already references. A fallback wrapper: try Ministral
// first, drop to gpt-oss if it fails, then Gemini as last resort. Renaming
// would mean editing all 12 `client Nvidia` sites for no gain, so the name
// stays despite Ministral not being NVIDIA-backed.
//
// KNOWN COST OF THIS ORDER, for ScoreArticles specifically: Ministral-3-14B
// judged with ±15 run-to-run variance on identical input and intermittently
// returned fewer results than it was given, which apply_scores reads as
// score 0 — i.e. a silent reject. gpt-oss-120b led for that reason until its
// provider latency made full runs impossible. Traded accuracy for a run that
// finishes; revisit when NVIDIA NIM recovers. See
// plans/scoring-recalibration.md.
client<llm> Nvidia {
  provider fallback
  options {
    strategy [Ministral, GptOss, Gemini]
  }
}
