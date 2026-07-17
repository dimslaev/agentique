from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from pipeline.sources.extract_content import extract_content
from pipeline.sources.utils import clean_title, fetch_with_timeout, is_within_window
from pipeline.types import FetchedArticle
from pipeline.utils import log

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item"
HN_FETCH_LIMIT = 200

HN_AI_KEYWORDS = re.compile(
    r"\b(ai|llm|gpt|claude|gemini|llama|openai|anthropic|deepseek|mistral|opencode|"
    r"tokens|transformer|diffusion|machine.?learning|deep.?learning|neural.?net|"
    r"language.?model|artificial.?intelligen|stable.?diffusion|midjourney|copilot|"
    r"chatbot|rag|fine.?tun|embedding|token|lora|rlhf|gguf|ollama|hugging.?face)\b",
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
            __import__("datetime")
            .datetime.fromtimestamp(
                item["time"], tz=__import__("datetime").timezone.utc
            )
            .isoformat()
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
                "published_date": pub_date
                or __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .isoformat(),
                "source": "Hacker News",
                "source_type": "hackerNews",
            }
        )

    log(f"Hacker News: {len(articles)} AI-related stories")
    return extract_content(articles)
