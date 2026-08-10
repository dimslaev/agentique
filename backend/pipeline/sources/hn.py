from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from pipeline.sources.extract_content import extract_content
from pipeline.sources.http import fetch_with_timeout
from pipeline.types import FetchedArticle
from pipeline.utils import clean_title, is_within_window, log

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item"
HN_FETCH_LIMIT = 200

# Title-only gate on HN's top stories. Recall matters more than precision — a
# missed story is gone, a false positive just costs one scored item — but a
# term that fires on non-AI posts every day is still a real cost, so broad
# company names ("google", "amd", "meta") are spelled out as the specific lab,
# chip, or product instead of matched bare.
HN_AI_KEYWORDS = re.compile(
    r"\b("
    # umbrella
    r"ai|agi|llm|slm|vlm|vla|genai|generative.?ai|artificial.?intelligen|"
    r"machine.?learning|deep.?learning|neural.?net|language.?model|"
    r"foundation.?model|frontier.?model|world.?model|reasoning.?model|"
    r"multimodal|vision.?language|superintelligence|chatbot|"
    # US / EU labs and their models
    r"openai|chatgpt|gpt|codex|sora|dall.?e|whisper|"
    r"anthropic|claude|"
    r"deepmind|gemini|gemma|veo|imagen|alphafold|alphago|notebooklm|"
    r"meta.?ai|llama|segment.?anything|"
    r"microsoft.?ai|copilot|phi.?[0-9]|maia|apple.?intelligence|"
    r"xai|grok|"
    r"mistral|mixtral|pixtral|codestral|devstral|magistral|ministral|"
    r"cohere|command.?r|ai21|jamba|"
    r"stability|stable.?diffusion|midjourney|black.?forest|flux\.?[0-9]|"
    r"runway|luma.?ai|pika|suno|udio|elevenlabs|heygen|synthesia|"
    r"perplexity|character\.?ai|inflection|adept|magic\.dev|reka|"
    r"liquid.?ai|nous.?research|eleutherai|allen.?institute|olmo|molmo|"
    r"sakana|thinking.?machines|safe.?superintelligence|world.?labs|"
    r"databricks|dbrx|arctic|nemotron|granite|"
    # Chinese labs and their models
    r"deepseek|qwen|qwq|alibaba.?cloud|"
    r"moonshot|kimi|"
    r"zhipu|z\.ai|glm.?[0-9]|chatglm|"
    r"minimax|"
    r"bytedance|doubao|seedream|seedance|seed.?oss|volcano.?engine|"
    r"tencent|hunyuan|baidu|ernie|huawei|pangu|ascend|"
    r"01\.ai|yi.?[0-9]|baichuan|internlm|shanghai.?ai.?lab|"
    r"stepfun|skywork|iflytek|sensetime|infinigence|longcat|meituan|"
    # accelerators
    r"nvidia|cuda|nvlink|tensor.?core|blackwell|hopper|"
    r"h100|h200|b100|b200|gb200|gb300|a100|rtx.?[0-9]|dgx|"
    r"rocm|mi300|mi325|mi355|instinct|"
    r"tpu|trillium|ironwood|trainium|inferentia|"
    r"groq|cerebras|tenstorrent|graphcore|sambanova|etched|furiosa|"
    r"npu|hbm[0-9]?|"
    # training / inference / serving
    r"transformer|attention|diffusion|mixture.?of.?experts|moe|"
    r"pre.?train|fine.?tun|post.?train|distill|quantiz|"
    r"rlhf|rlaif|rlvr|dpo|grpo|ppo|sft|"
    r"chain.?of.?thought|test.?time.?compute|"
    r"speculative.?decoding|kv.?cache|flash.?attention|paged.?attention|"
    r"context.?window|long.?context|tokenizer|tokens?|embedding|"
    r"lora|qlora|peft|awq|gptq|gguf|exllama|bitsandbytes|safetensors|"
    r"vllm|sglang|tensorrt|ollama|lm.?studio|mlx|"
    r"deepspeed|megatron|unsloth|axolotl|torchtitan|"
    r"pytorch|tensorflow|jax|triton|onnx|hugging.?face|"
    # agents / dev tools
    r"agentic|ai.?agent|coding.?agent|"
    r"cursor|windsurf|devin|cline|aider|opencode|amp.?code|"
    r"bolt\.new|lovable|replit.?agent|v0\.dev|"
    r"langchain|langgraph|llamaindex|autogen|crewai|dspy|pydantic.?ai|"
    r"mcp|model.?context.?protocol|"
    r"openrouter|together\.ai|fireworks.?ai|replicate|baseten|"
    r"rag|retrieval.?augmented|vector.?database|pgvector|"
    r"pinecone|weaviate|qdrant|milvus|chroma|"
    # evals
    r"mmlu|gpqa|humaneval|swe.?bench|arc.?agi|aime.?[0-9]|frontiermath|"
    r"livecodebench|lmarena|chatbot.?arena|lmsys|hallucinat|"
    # safety / policy
    r"alignment|interpretability|mechanistic|jailbreak|prompt.?injection|"
    r"red.?team|model.?welfare|ai.?safety|ai.?act|"
    # media generation
    r"text.?to.?image|text.?to.?video|text.?to.?speech|speech.?to.?text|"
    r"tts|asr|voice.?clon|"
    # data
    r"synthetic.?data|common.?crawl|fineweb"
    # Trailing [\d.]* absorbs version suffixes so "Qwen3", "GPT5" and "Llama4"
    # match the bare term. It can match empty, so the closing \b still keeps
    # "ai" from firing on "aircraft".
    r")[\d.]*\b",
    re.IGNORECASE,
)


def _fetch_item(item_id: int) -> dict | None:
    try:
        resp = fetch_with_timeout(f"{HN_ITEM}/{item_id}.json", timeout=10.0)
        return resp.json()
    except Exception:
        return None


def fetch_hn() -> list[FetchedArticle]:
    log("Fetching Hacker News top stories...")
    try:
        resp = fetch_with_timeout(HN_TOP)
        ids: list[int] = resp.json()
    except Exception as e:
        log(f"  HN top stories fetch failed: {e}")
        return []

    top_ids = ids[:HN_FETCH_LIMIT]

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(_fetch_item, top_ids))

    articles: list[FetchedArticle] = []
    for item in results:
        if not item or item.get("type") != "story" or not item.get("title"):
            continue
        if not HN_AI_KEYWORDS.search(item["title"]):
            continue
        pub_date = (
            datetime.fromtimestamp(item["time"], tz=UTC).isoformat()
            if item.get("time")
            else None
        )
        if not is_within_window(pub_date):
            continue
        articles.append(
            {
                "title": clean_title(item["title"]),
                "url": item.get("url")
                or f"https://news.ycombinator.com/item?id={item['id']}",
                "content": "",
                "published_date": pub_date or datetime.now(UTC).isoformat(),
                "source": "Hacker News",
            }
        )

    log(f"Hacker News: {len(articles)} AI-related stories")
    return extract_content(articles)
