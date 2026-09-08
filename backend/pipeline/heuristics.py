"""Deterministic rules the pipeline applies before (or instead of) asking an LLM,
plus the thresholds the steps are tuned around.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.catalog.models import ArticleKind
from pipeline.urls import hostname

# Tied to the rubric in baml_src/score.baml: the median in-scope article sits
# near 55 there, so this admits roughly the top third. Moving one without the
# other either empties the feed or fills it with newsletter filler.
SCORE_THRESHOLD = 65
PROMPT_CONTENT_CAP = 1500

# Below this, content is a teaser/blurb rather than an article, and the
# categorizer fails on it ~30-40% of the time (vs ~2% above it). Used to decide
# whether a fetched item still needs a network re-fetch of its full text.
MIN_CONTENT_CHARS = 500

# Title-only AI gate, applied wherever a source hands us far more items than we
# want to pay an LLM to read: Hacker News' firehose, and the broad engineering
# blogs marked ``Publisher.topic_gated`` (see ``steps.fetch.drop_off_topic``).
# Recall matters more than precision — a missed story is gone, a false positive
# just costs one scored item — but a term that fires on non-AI posts every day
# is still a real cost, so broad company names ("google", "amd", "meta") are
# spelled out as the specific lab, chip, or product instead of matched bare.
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

# Domains where a post is the release itself rather than someone's writeup of
# it. Two places lean on this: the scoring rubric floors these at 70, and the
# Hacker News source lets them past its traction gate — a lab's own announcement
# is real news at zero upvotes, and waiting for the votes would mean publishing
# it a day late, which is the whole reason the "new" firehose is polled.
FIRST_PARTY_HOSTS = frozenset(
    {
        "openai.com",
        "anthropic.com",
        "claude.com",
        "deepmind.google",
        "blog.google",
        "ai.meta.com",
        "ai.google.dev",
        "mistral.ai",
        "qwen.ai",
        "kimi.com",
        "moonshot.ai",
        "deepseek.com",
        "x.ai",
        "cohere.com",
        "ai21.com",
        "stability.ai",
        "allenai.org",
        "nvidia.com",
        "blogs.nvidia.com",
        "developer.nvidia.com",
        "research.google",
        "microsoft.com",
        "z.ai",
    }
)

# Owners whose repos are infrastructure by definition — a release branch or a
# PR under one of these is worth reading on day one, before it has stars of its
# own. Skips the star lookup in ``steps.filter.filter_thin_repos``.
KNOWN_REPO_OWNERS = frozenset(
    {
        "openai",
        "anthropics",
        "anthropic-experimental",
        "google",
        "google-deepmind",
        "google-research",
        "googleapis",
        "meta-llama",
        "facebookresearch",
        "pytorch",
        "tensorflow",
        "huggingface",
        "ggml-org",
        "ggerganov",
        "vllm-project",
        "sgl-project",
        "deepseek-ai",
        "qwenlm",
        "moonshotai",
        "mistralai",
        "nvidia",
        "microsoft",
        "modelcontextprotocol",
        "ollama",
        "langchain-ai",
        "run-llama",
        "unslothai",
        "triton-lang",
        "openvinotoolkit",
        "mlx-explore",
        "apple",
        "allenai",
        "eleutherai",
        "bytedance",
        "tencent",
        "zai-org",
        "baai-agents",
    }
)

NON_REPO_OWNERS = {
    "features",
    "login",
    "pricing",
    "about",
    "marketplace",
    "explore",
    "topics",
    "collections",
    "trending",
    "sponsors",
    "orgs",
    "apps",
    "contact",
    "security",
}

GITHUB_REPO_RE = re.compile(
    r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
)


def github_repo_from_content(content: str) -> str | None:
    match = GITHUB_REPO_RE.search(content)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    if owner.lower() in NON_REPO_OWNERS:
        return None
    return f"https://github.com/{owner}/{repo}"


def is_first_party(url: str) -> bool:
    """True when the URL is a lab publishing on its own domain.

    Matches subdomains too (``platform.claude.com``, ``blog.mistral.ai``), so a
    lab moving its newsroom to a subdomain does not silently drop out of the
    fast path. ``huggingface.co`` is deliberately absent as a bare host - it is
    mostly user-uploaded - so only its editorial blog qualifies.
    """
    host = hostname(url)
    if not host:
        return False
    if host in ("huggingface.co", "hf.co"):
        return urlparse(url).path.startswith("/blog")
    return any(host == h or host.endswith(f".{h}") for h in FIRST_PARTY_HOSTS)


def github_repo_from_url(url: str) -> tuple[str, str] | None:
    """``(owner, repo)`` for a github.com URL that names a repository, else None.

    Handles every shape a link lands in — the repo root, a PR, an issue, a blob
    or a tree path — because they all start ``/owner/repo``. Anything else on
    the host (a user profile, ``/features``, gist.github.com) is not a repo and
    returns None rather than a bogus pair.
    """
    if hostname(url) != "github.com":
        return None
    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if owner.lower() in NON_REPO_OWNERS:
        return None
    return owner, repo.removesuffix(".git")


def kind_from_url(url: str) -> ArticleKind | None:
    """Deterministic ArticleKind from a URL host, or None if inconclusive."""
    host = hostname(url)
    if host in ("github.com", "gitlab.com"):
        return ArticleKind.repo
    if host in ("huggingface.co", "hf.co"):
        return ArticleKind.model
    if host in ("arxiv.org", "ar5iv.labs.arxiv.org"):
        return ArticleKind.paper
    return None


# TRUST_BY_SOURCE removed under the new schema: per-article trust now comes from
# Publisher.trust (resolved via pipeline.publishers), not a hard-coded map.
