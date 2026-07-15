// Primary scorer: gpt-oss-120b is the highest-quality judge but times out under
// load, so it gets a generous timeout and falls back to Ministral.
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
    base_url "https://integrate.api.nvidia.com/v1"
    api_key env.NVIDIA_NIM_API_KEY
    model "mistralai/ministral-14b-instruct-2512"
    timeout 120
  }
}

// The name every function already references. Now a fallback wrapper: try
// gpt-oss first, drop to Ministral only if it keeps failing. Renaming would
// mean editing all 12 `client Nvidia` sites for no gain; both are NVIDIA NIM.
client<llm> Nvidia {
  provider fallback
  options {
    strategy [GptOss, Ministral]
  }
}
