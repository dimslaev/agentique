"""Print the old search and the hybrid search side by side, for reading.

The old search ranked by the embedding alone. Run from `backend/` against a
local db restored from a prod dump: `uv run python scripts/search_eval.py`.
Pass queries as arguments to use them in place of the default set.
"""

from __future__ import annotations

import sys
import time

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import cast, text
from sqlmodel import Session, col, select

from app.core.db.article import Article
from app.core.db.engine import engine
from app.features.catalog.search import embed, search

TOP = 10
QUERY_COUNT = 30
WIDTH = 58

# Used when the db has logged fewer than QUERY_COUNT searches.
HAND_WRITTEN = [
    "MCP",
    "gpt-4o",
    "vLLM",
    "Claude Code",
    "AGENTS.md",
    "llama.cpp",
    "SWE-bench",
    "DSPy",
    "ollama",
    "LangGraph",
    "o3-mini",
    "text-to-SQL",
    "prompt caching",
    "agent memory",
    "tool calling",
    "structured output",
    "context engineering",
    "prompt injection",
    "vector database",
    "quantization",
    "browser agents",
    "agent sandbox",
    "RAG evaluation",
    "evals for coding agents",
    "multi-agent orchestration",
    "fine-tuning small models",
    "speech to text",
    "how do I run a model locally",
    "cost of running inference",
    "what changed in the latest Claude release",
]


def logged_queries(session: Session) -> list[str]:
    """The searches readers ran most, as the website logged them."""
    rows = session.connection().execute(
        text(
            "SELECT lower(props->>'query') AS q FROM analytics_event"
            " WHERE event = 'search' AND props->>'query' IS NOT NULL"
            " GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT :n"
        ),
        {"n": QUERY_COUNT},
    )
    return [row.q for row in rows]


def old_search(session: Session, q: str) -> list[str]:
    distance = cast(Article.embedding, Vector(256)).cosine_distance(embed(q))
    return list(
        session.exec(
            select(Article.title)
            .where(col(Article.embedding).is_not(None))
            .order_by(distance, col(Article.id).desc())
            .limit(TOP)
        )
    )


def main() -> None:
    with Session(engine) as session:
        queries = sys.argv[1:]
        if not queries:
            logged = logged_queries(session)
            queries = logged + [q for q in HAND_WRITTEN if q.lower() not in logged]
            queries = queries[:QUERY_COUNT]
        # The first call loads the model, which would count against one query.
        embed("warm up")
        for q in queries:
            start = time.perf_counter()
            old = old_search(session, q)
            between = time.perf_counter()
            hybrid = [a.title for a in search(session, q, TOP).data]
            old_ms = (between - start) * 1000
            hybrid_ms = (time.perf_counter() - between) * 1000
            print(f"\n== {q} ==  old {old_ms:.0f} ms, hybrid {hybrid_ms:.0f} ms")
            print(f"    {'old (embedding only)':{WIDTH}}  hybrid (* not in old)")
            for i in range(max(len(old), len(hybrid))):
                left = old[i][:WIDTH] if i < len(old) else ""
                right = hybrid[i] if i < len(hybrid) else ""
                mark = "*" if right and right not in old else " "
                print(f"{i + 1:2}  {left:{WIDTH}} {mark}{right[:WIDTH]}")


if __name__ == "__main__":
    main()
