import pytest

from pipeline.sources.hn import HN_AI_KEYWORDS

MATCHES = [
    # version suffixes glued to the name — the case bare \b boundaries miss
    "Qwen3-Max is out",
    "Llama4 Scout weights",
    "GPT5 system card",
    "Gemma3 on device",
    "Qwen2.5-VL",
    # Chinese labs
    "Kimi K2 thinking",
    "GLM-4.6 released",
    "MiniMax M2",
    "Hunyuan video model",
    "Ernie 5.0",
    "Huawei Pangu weights",
    # accelerators
    "Nvidia GB200 NVL72 teardown",
    "MI355X vs H200 throughput",
    "Cerebras hits 3000 tok/s",
    "Ironwood TPU",
    "Tenstorrent Blackhole",
    # training / serving
    "vLLM adds speculative decoding",
    "GRPO from scratch",
    "Ollama now supports MLX",
    # agents / tools / evals / safety
    "MCP servers explained",
    "SWE-bench verified results",
    "Prompt injection in Copilot",
    "Mechanistic interpretability of induction heads",
]

# Non-AI titles that a sloppy pattern would catch — mostly prefix collisions
# with the short umbrella terms ("ai", "rag").
NON_MATCHES = [
    "Postgres 18 released",
    "A new CSS layout engine",
    "Rust 1.90 is out",
    "SQLite internals",
    "Aircraft carrier design",
    "Ragged arrays in C",
    "Aiming for simplicity",
    "Airbnb redesign",
    "The economics of shipping containers",
]


@pytest.mark.parametrize("title", MATCHES)
def test_matches_ai_titles(title: str) -> None:
    assert HN_AI_KEYWORDS.search(title)


@pytest.mark.parametrize("title", NON_MATCHES)
def test_skips_non_ai_titles(title: str) -> None:
    assert not HN_AI_KEYWORDS.search(title)
