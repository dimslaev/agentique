"""The title-only AI gate: is this item about AI at all, judged by title alone?

Applied wherever a source hands us far more items than we want to pay an LLM to
read, and always ahead of every DB, DNS, embedding and LLM cost — so an
off-topic item costs one regex and nothing else.
"""

from __future__ import annotations

import re

AI_TITLE_KEYWORDS = re.compile(
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


def is_on_topic(title: str) -> bool:
    """True when a title names anything on the AI map above.

    The interface the gate is used through — callers ask the question, they do
    not reach for the regex. See ``AI_TITLE_KEYWORDS`` for the recall/precision
    trade-off the term list is tuned around.
    """
    return bool(AI_TITLE_KEYWORDS.search(title))
