"""Hacker News source: polls the newstories/newest feed and applies the traction gate."""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from app.platform.logging import log
from pipeline.fetching.http import fetch_with_timeout
from pipeline.first_party import is_first_party
from pipeline.freshness import is_within_window
from pipeline.titles import clean_title
from pipeline.types import RawItem

HN_ITEM = "https://hacker-news.firebaseio.com/v0/item"


def hn_min_points() -> int:
    """Upvotes an aged-out story needs before it is worth an extraction and a
    scoring call. 0 disables the traction gate.

    A Show HN for a two-star repo finishes its life at 1-4 points; anything the
    community actually read clears 10 comfortably.
    """
    return int(os.environ.get("HN_MIN_POINTS", "10"))


def hn_min_comments() -> int:
    """Alternative to ``hn_min_points``: a story that got discussed is real even
    when the votes stayed flat. Either bar clears the gate."""
    return int(os.environ.get("HN_MIN_COMMENTS", "5"))


def hn_grace_hours() -> float:
    """How long a story is exempt from having any traction yet.

    Under this age a vote count says nothing - every story starts at 1 point.
    Rather than admit them blind (which is what filled the feed with noise) the
    source holds them back; the next run re-reads them with real numbers, still
    inside the 48h window.
    """
    return float(os.environ.get("HN_GRACE_HOURS", "6"))


# The title-only AI gate. Moved here from pipeline/topic_gate.py when the
# pipeline stopped gating feeds by topic: HN is the one source whose firehose
# is mostly not about AI, so it keeps the gate.
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
    r"synthetic.?data|common.?crawl|fineweb|"
    # generic terms the list above misses: broad enough to let a post through
    # on its own words rather than on naming a vendor.
    r"gpu|inference|evals?|evaluation|benchmark|harness|subagent|skills?|"
    r"vibe.?cod|context.?engineering|on.?device|local.?(?:llm|model)|prompt|"
    # model and product names in the feed but not named above. Everyday English
    # words (opus, sonnet, haiku, nova, muse, needle) are here on purpose: this
    # gate is tuned for recall, and a false positive only costs the agent a
    # title to read. The list churns monthly -- review it against the titles
    # the gate misses whenever the feed feels thin:
    #   SELECT title FROM article ORDER BY created_at DESC LIMIT 500;
    # then re-run is_on_topic over them and read what fails.
    r"fable|astra|opus|sonnet|haiku|nova|muse|hermes|needle|holotron|lfm"
    # Trailing [\d.]* absorbs version suffixes so "Qwen3", "GPT5" and "Llama4"
    # match the bare term. It can match empty, so the closing \b still keeps
    # "ai" from firing on "aircraft".
    r")[\d.]*\b",
    re.IGNORECASE,
)


def is_on_topic(title: str) -> bool:
    """True when a title names anything on the AI map above.

    HN's keyword gate: the front page and the "new" firehose are mostly not
    about AI, and this runs before any item is fetched in full. See
    ``AI_TITLE_KEYWORDS`` for the recall/precision trade-off the term list is
    tuned around.
    """
    return bool(AI_TITLE_KEYWORDS.search(title))


# Two firehoses, both title-gated by is_on_topic before any item is
# fetched in full. "top" is the front page — high signal, but an AI post only
# reaches it if it already trended. "new" is every submission in publication
# order, which is where a lab's own release lands minutes after it goes up and
# often never climbs any higher. Together they roughly double HN reach for the
# cost of a few hundred extra id lookups (a JSON blob each, no LLM involved).
HN_FEEDS = (
    ("top", "https://hacker-news.firebaseio.com/v0/topstories.json"),
    ("new", "https://hacker-news.firebaseio.com/v0/newstories.json"),
)
HN_FETCH_LIMIT = 200


def _fetch_item(item_id: int) -> dict | None:
    try:
        resp = fetch_with_timeout(f"{HN_ITEM}/{item_id}.json", timeout=10.0)
        return resp.json()
    except Exception:
        return None


def _story_ids(label: str, url: str) -> list[int]:
    try:
        resp = fetch_with_timeout(url)
        ids: list[int] = resp.json()
    except Exception as e:
        log(f"  HN {label} stories fetch failed: {e}")
        return []
    return ids[:HN_FETCH_LIMIT]


def _age_hours(item: dict) -> float | None:
    """Hours since the story was posted, or None if it carries no timestamp."""
    posted = item.get("time")
    if not posted:
        return None
    return (datetime.now(UTC).timestamp() - float(posted)) / 3600


def _passes_topic_and_window(item: dict) -> bool:
    """Every ``_to_article`` gate except traction — the denominator the run log
    reports the traction gate against."""
    if not item or item.get("type") != "story" or not item.get("title"):
        return False
    if not is_on_topic(item["title"]):
        return False
    posted = item.get("time")
    pub_date = datetime.fromtimestamp(posted, tz=UTC).isoformat() if posted else None
    return is_within_window(pub_date)


def has_traction(item: dict) -> bool:
    """Has HN itself said this story is worth reading?

    The firehose is not an editorial feed — ``newstories`` is every submission,
    so a two-star repo posted by its author sits there next to a frontier
    release, and both look identical from title and URL alone. Points and
    comments are HN's own verdict on which is which, they ride along in the item
    JSON we already fetch, and until now the pipeline threw them away.

    Three cases:

    * **First-party lab post** — through regardless. A release on openai.com is
      news at zero points, and the whole reason ``newstories`` is polled is to
      catch it in the minutes before it trends.
    * **Still young** (under ``hn_grace_hours``) — no verdict yet. Every story
      starts at 1 point, so a vote count here means nothing either way, and this
      returns False to *hold the story back rather than reject it*: nothing
      dropped in a source is recorded as a reject, so the next run re-reads
      the same id with settled numbers, still inside the 48h recency window.
      The cost is up to a day of latency on a non-lab story; the alternative is
      admitting the entire firehose blind, which is what filled the feed with
      noise.
    * **Aged out** — judged on ``hn_min_points`` upvotes or ``hn_min_comments``
      comments, either bar. A story that has been up half a day with neither is
      one nobody read, and that is the signal, not a proxy for it.

    Set ``HN_MIN_POINTS=0`` to turn the gate off entirely.
    """
    if hn_min_points() <= 0:
        return True
    if is_first_party(item.get("url") or ""):
        return True

    age = _age_hours(item)
    if age is not None and age < hn_grace_hours():
        return False

    points = item.get("score") or 0
    comments = item.get("descendants") or 0
    return points >= hn_min_points() or comments >= hn_min_comments()


def _to_article(item: dict) -> RawItem | None:
    """One HN item -> a fetched article, or None if it fails a gate.

    Gates, cheapest first: it must be a titled story, its title must look
    AI-related, it must fall inside the pipeline's recency window, and HN's own
    readers must have given it some traction. Content stays empty here: the
    fetch step (``steps.fetch._with_content``) fetches the full text, as it
    does for every thin source.
    """
    if not item or item.get("type") != "story" or not item.get("title"):
        return None
    if not is_on_topic(item["title"]):
        return None
    pub_date = (
        datetime.fromtimestamp(item["time"], tz=UTC).isoformat()
        if item.get("time")
        else None
    )
    if not is_within_window(pub_date):
        return None
    if not has_traction(item):
        return None
    points = item.get("score") or 0
    comments = item.get("descendants") or 0
    return {
        "title": clean_title(item["title"]),
        "url": item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}",
        "content": "",
        "published_date": pub_date or datetime.now(UTC).isoformat(),
        "source": "Hacker News",
        # Shown to the curation agent, not just used as a gate: told that a
        # submission is a Show HN sitting at 3 points, it stops reading the
        # title as if it were an announcement.
        "traction": f"{points} points, {comments} comments on Hacker News",
    }


def fetch_hn() -> list[RawItem]:
    log("Fetching Hacker News top + new stories...")

    # The two lists overlap heavily (a new story that trends is on both), so
    # dedupe ids before spending a lookup on them.
    seen_ids: set[int] = set()
    ids: list[int] = []
    for label, url in HN_FEEDS:
        for item_id in _story_ids(label, url):
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                ids.append(item_id)

    if not ids:
        return []

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(_fetch_item, ids))

    seen_urls: set[str] = set()
    articles: list[RawItem] = []
    on_topic = 0
    for item in results:
        item = item or {}
        # Counted before the traction gate only, so the log separates "HN had
        # nothing about AI today" from "it did, and none of it had been read".
        if _passes_topic_and_window(item):
            on_topic += 1
        article = _to_article(item)
        if article is None or article["url"] in seen_urls:
            continue
        seen_urls.add(article["url"])
        articles.append(article)

    log(
        f"Hacker News: {len(articles)} of {on_topic} AI-related stories have "
        f"traction (>={hn_min_points()} points or >={hn_min_comments()} comments "
        f"after {hn_grace_hours():g}h); {len(ids)} ids scanned"
    )
    return articles
