client<llm> Nvidia {
  provider openai-generic
  options {
    base_url "https://integrate.api.nvidia.com/v1"
    api_key env.NVIDIA_NIM_API_KEY
    model "mistralai/ministral-14b-instruct-2512"
    timeout 60
  }
}
