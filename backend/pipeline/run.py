"""Pipeline entry point. Run with: python -m pipeline.run"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

from model2vec import StaticModel
from sqlmodel import Session, create_engine, select

from app.models_agentique import (
    Article,
    ArticleKind,
    Category,
    Publisher,
    ScoredUrl,
)
from baml_client.sync_client import b
from baml_client.types import ArticleInput, ExistingArticle, TagInput, TagOption
from pipeline import keep_drop
from pipeline.health import (
    RunStats,
    check_liveness,
    record_run,
    verify_run,
)
from pipeline.publishers import (
    PublisherResolver,
    feed_sources_from_db,
    newsletter_senders_from_db,
)
from pipeline.sources.ainews import fetch_ai_news
from pipeline.sources.email import fetch_newsletter
from pipeline.sources.extract_content import re_extract_full_content
from pipeline.sources.hn import fetch_hn
from pipeline.sources.substack import fetch_feeds
from pipeline.steps import (
    PROMPT_CONTENT_CAP,
    SCORE_THRESHOLD,
    github_repo_from_content,
    kind_from_url,
)
from pipeline.tags import Vocabulary, load_vocabulary, validate_tags, write_article_tags
from pipeline.utils import (
    is_valid_summary,
    is_valid_title,
    log,
    sanitize_llm_text,
    strip_title_wrappers,
    wait_ms,
)


def _build_db_url() -> str:
    server = os.environ["POSTGRES_SERVER"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ["POSTGRES_USER"]
    password = os.environ.get("POSTGRES_PASSWORD", "")
    db = os.environ.get("POSTGRES_DB", "")
    return f"postgresql+psycopg://{user}:{password}@{server}:{port}/{db}"


_engine = create_engine(_build_db_url())

_model: StaticModel | None = None


def _get_model() -> StaticModel:
    global _model
    if _model is None:
        _model = StaticModel.from_pretrained("minishlab/potion-base-8M")
    return _model


def _embed(text: str) -> list[float]:
    return _get_model().encode([text])[0].tolist()


def _build_sources(session: Session) -> list[dict]:
    """Assemble the run's sources. Aggregator channels (HN, AI News) keep their
    fetchers; RSS/substack feeds and IMAP newsletter senders are both DB-driven
    — "Feeds" polls every active feed publisher, "Newsletter" matches unread
    mail against every active publisher with an ``email`` link.
    """
    return [
        {"label": "Hacker News", "fetcher": fetch_hn},
        {
            "label": "Newsletter",
            "fetcher": lambda: fetch_newsletter(newsletter_senders_from_db(session)),
        },
        {"label": "AI News", "fetcher": fetch_ai_news},
        {
            "label": "Feeds",
            "fetcher": lambda: fetch_feeds(feed_sources_from_db(session)),
        },
    ]


def _to_baml_input(a: dict) -> ArticleInput:
    """Build a BAML ArticleInput from a fetched-article dict (snippet capped at
    200). ``trust`` is stamped by _resolve_publishers from Publisher.trust."""
    return ArticleInput(
        url=a["url"],
        title=a["title"],
        source=a["source"],
        snippet=a.get("content", "")[:200] if a.get("content") else None,
        trust=a.get("trust"),
    )


def run_pipeline(stats: RunStats) -> None:
    log("=== Pipeline start ===")

    with Session(_engine) as session:
        resolver = PublisherResolver(session=session)
        vocab = load_vocabulary(session)

        for src in _build_sources(session):
            label = src["label"]
            log(f"\n=== Processing {label} ===")
            s = stats.source(label)

            try:
                fetched = _fetch_source(src["fetcher"], label)
                s.fetched = len(fetched)

                _resolve_publishers(fetched, resolver)

                fresh = _filter_known_urls(session, fetched, label)
                s.filtered_known = s.fetched - len(fresh)

                alive = _filter_dead_domains(fresh, label)
                s.filtered_dead = len(fresh) - len(alive)

                unique = _dedup_semantic(session, alive, label)
                s.deduped = len(alive) - len(unique)

                candidates = _prefilter_keep_drop(session, unique)
                scored = _score_articles(session, candidates)
                # below_threshold = pre-filter drops + gpt-oss sub-threshold
                s.below_threshold = len(unique) - len(scored)

                inserted = _insert_articles(session, scored)
                s.inserted = len(inserted)

                _improve_titles(session, inserted)
                with_content = _extract_full_content(session, inserted)
                processed = _summarize_and_categorize(session, with_content)
                _assign_tags(session, processed, vocab)
                _embed_articles(session, processed)
            except Exception as e:
                # One source failing must not sink the others — record and move on.
                s.errors.append(f"{type(e).__name__}: {e}")
                log(f"  !! {label} failed: {e}")
                session.rollback()

        if resolver.quarantined:
            log(
                f"\n{len(resolver.quarantined)} publisher(s) quarantined this run: "
                f"{', '.join(resolver.quarantined)}"
            )

    log("=== Pipeline complete ===")


# ─── Step 01b: publisher resolution ───────────────────────────────────────────


def _resolve_publishers(articles: list[dict], resolver: PublisherResolver) -> None:
    """Stamp each fetched item in place with publisher_id and trust.

    Both come from the Publisher row (resolved by source name, auto-quarantined
    if unknown). Runs right after fetch so trust is available to the
    scoring/dedup BAML calls.
    """
    for a in articles:
        publisher = resolver.resolve(a["source"])
        a["publisher_id"] = publisher.id
        a["trust"] = publisher.trust.value


# ─── Step 01 ────────────────────────────────────────────────────────────────


def _fetch_source(fetcher, label: str) -> list[dict]:
    articles = fetcher()
    if not articles:
        log(f"No articles from {label}")
    return articles


# ─── Step 02 ────────────────────────────────────────────────────────────────


def _filter_known_urls(
    session: Session, articles: list[dict], label: str
) -> list[dict]:
    if not articles:
        return []
    all_urls = [a["url"] for a in articles]

    existing_urls = set(
        session.exec(select(Article.url).where(Article.url.in_(all_urls))).all()
    )
    scored_urls = set(
        session.exec(select(ScoredUrl.url).where(ScoredUrl.url.in_(all_urls))).all()
    )

    fresh = [
        a
        for a in articles
        if a["url"] not in existing_urls and a["url"] not in scored_urls
    ]

    if existing_urls or scored_urls:
        log(
            f"  Filtered {len(existing_urls)} known + {len(scored_urls)} already-scored URLs"
        )
    if not fresh:
        log(f"  No new articles from {label}")
        return []
    log(f"  {len(fresh)} new articles to process")
    return fresh


# ─── Step 02b ───────────────────────────────────────────────────────────────


def _filter_dead_domains(articles: list[dict], label: str) -> list[dict]:
    if not articles:
        return articles

    from urllib.parse import urlparse

    import dns.resolver

    def is_resolvable(url: str) -> bool:
        try:
            host = urlparse(url).hostname
            if not host:
                return False
            dns.resolver.resolve(host, "A")
            return True
        except dns.resolver.NXDOMAIN:
            return False
        except Exception:
            return True  # Other errors (timeout, etc.) - assume alive

    results = [(a, is_resolvable(a["url"])) for a in articles]
    alive = [a for a, ok in results if ok]
    dead = [a for a, ok in results if not ok]
    for a in dead:
        log(f"  Dropped dead URL: {a['url']}")
    if dead:
        log(f"  Filtered {len(dead)} dead-domain URLs from {label}")
    return alive


# ─── Step 03 ────────────────────────────────────────────────────────────────


def _dedup_semantic(session: Session, articles: list[dict], label: str) -> list[dict]:
    if not articles:
        return articles

    cutoff = datetime.now(UTC) - timedelta(days=14)
    recent_db = session.exec(
        select(Article).where(Article.published_at >= cutoff)
    ).all()

    if not recent_db:
        return articles

    log(f"  Deduplicating against {len(recent_db)} recent DB articles...")

    # Publisher name is only used for display in the dedup prompt. Resolve the
    # ids in one query so ExistingArticle.source stays populated post-refactor.
    pub_ids = {art.publisher_id for art in recent_db}
    pub_names = {
        p.id: p.name
        for p in session.exec(select(Publisher).where(Publisher.id.in_(pub_ids))).all()
    }

    new_inputs = [_to_baml_input(a) for a in articles]
    existing_inputs = [
        ExistingArticle(
            url=str(art.url),
            title=art.title,
            source=pub_names.get(art.publisher_id, ""),
        )
        for art in recent_db
    ]

    try:
        matches = b.SemanticDedup(new_inputs, existing_inputs)
        merged_urls = {m.url for m in matches}
        for m in matches:
            log(f"  Dropped duplicate: {m.url} (matches existing: {m.existingUrl})")
        if merged_urls:
            log(f"  {len(merged_urls)} articles dropped as duplicates")
        unique = [a for a in articles if a["url"] not in merged_urls]
        if not unique:
            log(f"  No new unique articles from {label}")
        return unique
    except Exception as e:
        log(f"  Dedup failed, continuing without: {e}")
        return articles


# ─── Step 04 ────────────────────────────────────────────────────────────────


def _prefilter_keep_drop(session: Session, articles: list[dict]) -> list[dict]:
    """Cascade pre-filter: drop obvious junk before the gpt-oss scorer.

    Runs the tiny distilled classifier on title+snippet. Anything it is very
    confident is a drop (P(keep) < keep_drop.DROP_BELOW) is discarded without a
    gpt-oss call and recorded in ScoredUrl so it is not re-fetched. Everything
    else passes through for real scoring. gpt-oss stays the scoring authority.
    """
    if not articles or keep_drop.DROP_BELOW <= 0:
        return articles

    strings = [keep_drop.serialize(a["title"], a.get("content")) for a in articles]
    vecs = _get_model().encode(strings)

    survivors, dropped = [], 0
    for a, vec in zip(articles, vecs):
        if keep_drop.keep_proba(vec) < keep_drop.DROP_BELOW:
            session.merge(ScoredUrl(url=a["url"]))
            dropped += 1
        else:
            survivors.append(a)
    if dropped:
        session.commit()

    log(
        f"  Pre-filter dropped {dropped}/{len(articles)} as obvious junk "
        f"(P(keep) < {keep_drop.DROP_BELOW}); {len(survivors)} to scorer"
    )
    return survivors


def _score_articles(session: Session, articles: list[dict]) -> list[dict]:
    if not articles:
        return []

    log(f"  Scoring {len(articles)} articles in batches of 5...")

    BATCH = 5
    all_scores: list[dict] = []
    for i in range(0, len(articles), BATCH):
        batch_inputs = [_to_baml_input(a) for a in articles[i : i + BATCH]]
        result = b.ScoreArticles(batch_inputs)
        all_scores.extend({"url": r.url, "score": r.score} for r in result)
        log(f"    batch {i // BATCH + 1}/{(len(articles) + BATCH - 1) // BATCH} done")
        wait_ms(1000)

    score_by_url = {s["url"]: s["score"] for s in all_scores}
    scored = []
    for a in articles:
        score = score_by_url.get(a["url"], 0)
        # TODO(new-schema): hard-coded per-source score bonus. Once publishers
        # carry a boost/weight field this should read from the Publisher row
        # (a["trust"] is already available) instead of matching a name string.
        if a["source"] == "Ben's Bites":
            score = min(score + 10, 100)
        scored.append({**a, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    kept = [s for s in scored if s["score"] >= SCORE_THRESHOLD]
    log(f"  {len(kept)} articles pass scoring (threshold: {SCORE_THRESHOLD})")

    # Record ALL evaluated URLs (including sub-threshold)
    for a in articles:
        session.merge(ScoredUrl(url=a["url"]))
    session.commit()

    return kept


# ─── Step 05 ────────────────────────────────────────────────────────────────


def _insert_articles(session: Session, scored: list[dict]) -> list[dict]:
    if not scored:
        return []

    by_url: dict[str, dict] = {}
    for item in scored:
        existing = by_url.get(item["url"])
        if not existing or item["score"] > existing["score"]:
            by_url[item["url"]] = item

    inserted = []
    for item in by_url.values():
        item["title"] = sanitize_llm_text(item["title"])
        pub_at = None
        if item.get("published_date"):
            try:
                from email.utils import parsedate_to_datetime

                try:
                    pub_at = parsedate_to_datetime(item["published_date"])
                except Exception:
                    pub_at = datetime.fromisoformat(
                        item["published_date"].replace("Z", "+00:00")
                    )
            except Exception:
                pass

        article = Article(
            title=item["title"],
            publisher_id=item["publisher_id"],
            url=item["url"],
            published_at=pub_at,
            score=item["score"],
            content=item.get("content") or "",
        )
        session.add(article)
        session.flush()
        assert article.id is not None
        log(f"  Inserted #{article.id}: [{item['score']}/100] {item['title']}")
        inserted.append({**item, "id": article.id})

    session.commit()
    return inserted


# ─── Step 06 ────────────────────────────────────────────────────────────────


def _improve_titles(session: Session, inserted: list[dict]) -> None:
    if not inserted:
        return

    log(f"  Improving {len(inserted)} titles...")

    for item in inserted:
        art_id = item["id"]
        try:
            fixes = b.ImproveTitles([_to_baml_input(item)])
            raw = fixes[0].title if fixes else None
            if not raw:
                continue
            sanitized = strip_title_wrappers(sanitize_llm_text(raw))
            if not sanitized or sanitized == item["title"]:
                continue
            if not is_valid_title(sanitized):
                log(f'  Skip rewrite #{art_id} (malformed): "{sanitized[:80]}"')
                continue
            if item["source"].lower() in sanitized.lower():
                log(f'  Skip rewrite #{art_id} (source name leaked): "{sanitized}"')
                continue
            old_title = item["title"]
            article = session.get(Article, art_id)
            if article:
                article.title = sanitized
                session.add(article)
                session.commit()
            item["title"] = sanitized
            log(f'  Improved title #{art_id}: "{old_title}" → "{sanitized}"')
        except Exception as e:
            log(f"  Title improve failed for #{art_id}, continuing: {e}")


# ─── Step 07 ────────────────────────────────────────────────────────────────


def _extract_full_content(session: Session, inserted: list[dict]) -> list[dict]:
    if not inserted:
        return []

    to_extract = [a for a in inserted if a["source_type"] != "aiNews"]
    content_map = re_extract_full_content([{"url": a["url"]} for a in to_extract])

    for item in to_extract:
        full = content_map.get(item["url"])
        if full:
            article = session.get(Article, item["id"])
            if article:
                article.content = full
                session.add(article)
    session.commit()

    result = []
    for item in inserted:
        full = content_map.get(item["url"]) or item.get("content", "")
        result.append({**item, "full_content": full})
    return result


# ─── Step 08 ────────────────────────────────────────────────────────────────


def _to_categories(baml_categories) -> list[Category]:
    """Map BAML ArticleCategory enum values -> Category enum, dropping unknowns."""
    out: list[Category] = []
    for c in baml_categories:
        value = getattr(c, "value", c)
        try:
            out.append(Category(str(value).lower()))
        except ValueError:
            log(f"  Dropped unknown category {value!r}")
    return out


def _to_kind(baml_kind) -> ArticleKind | None:
    """Map a BAML ArticleKind enum value -> models ArticleKind enum."""
    value = getattr(baml_kind, "value", baml_kind)
    try:
        return ArticleKind(str(value).lower())
    except ValueError:
        log(f"  Dropped unknown kind {value!r}")
        return None


def _summarize_and_categorize(session: Session, items: list[dict]) -> list[dict]:
    if not items:
        return []

    log(f"  Summarizing and categorizing {len(items)} articles...")
    processed = []

    for item in items:
        art_id = item["id"]
        full_content = item.get("full_content", "")
        summary = ""
        categories: list[Category] = []
        # kind_from_url returns an ArticleKind (or None if inconclusive).
        kind: ArticleKind | None = kind_from_url(item["url"])

        try:
            if full_content:
                result = b.SummarizeAndCategorize(
                    item["title"], full_content[:PROMPT_CONTENT_CAP]
                )
                summary = sanitize_llm_text(result.summary or "")
                if summary and not is_valid_summary(summary):
                    log(f'  Drop summary #{art_id} (malformed): "{summary[:80]}"')
                    summary = ""
                categories = _to_categories(result.categories)
                if not kind:
                    kind = _to_kind(result.kind)
                if kind == ArticleKind.blog and github_repo_from_content(full_content):
                    kind = ArticleKind.repo
            else:
                result = b.CategorizeOnly(item["title"])
                categories = _to_categories(result.categories)
                if not kind:
                    kr = b.ClassifyKind(item["title"], item["url"], None)
                    kind = _to_kind(kr.kind)
        except Exception as e:
            log(f"  Summarize/categorize failed for #{art_id}: {e}")

        article = session.get(Article, art_id)
        if article:
            article.summary = summary
            article.categories = categories
            if kind:
                article.kind = kind
            session.add(article)

        processed.append(
            {
                "id": art_id,
                "url": item["url"],
                "title": item["title"],
                "score": item["score"],
                "summary": summary,
                "categories": categories,
            }
        )

    session.commit()
    log("  Done summarizing and categorizing")
    return processed


# ─── Step 08b: tag assignment (the main new LLM step) ─────────────────────────


TAG_BATCH = 10


def _assign_tags(session: Session, items: list[dict], vocab: Vocabulary) -> None:
    """Assign 1-3 tags per article from the DB-backed vocabulary and write
    ArticleTag rows. Batched by article id; the vocabulary is passed to the LLM
    as a parameter, and output is validated against it — off-list tags are
    dropped and no tag is ever created at runtime (see pipeline.tags)."""
    if not items:
        return

    log(f"  Assigning tags to {len(items)} articles ({len(vocab.slugs)} tags)...")

    options = [
        TagOption(slug=slug, description=desc or None)
        for slug, desc in sorted(vocab.slug_to_description.items())
    ]

    for i in range(0, len(items), TAG_BATCH):
        batch = items[i : i + TAG_BATCH]
        inputs = [
            TagInput(
                articleId=it["id"],
                title=it["title"],
                summary=it.get("summary") or None,
            )
            for it in batch
        ]
        try:
            assignments = b.AssignTags(inputs, options)
        except Exception as e:
            log(f"  Tag assignment failed for batch {i // TAG_BATCH + 1}: {e}")
            continue

        for a in assignments:
            slugs = validate_tags(list(a.tags), vocab.slugs)
            write_article_tags(session, a.articleId, slugs, vocab)
        wait_ms(1000)

    session.commit()
    log("  Done assigning tags")


# ─── Step 09 ────────────────────────────────────────────────────────────────


def _embed_articles(session: Session, items: list[dict]) -> None:
    if not items:
        return

    log(f"  Embedding {len(items)} articles...")

    for item in items:
        art_id = item["id"]
        try:
            text = (
                f"{item['title']}\n\n{item['summary']}"
                if item.get("summary")
                else item["title"]
            )
            vec = _embed(text)
            article = session.get(Article, art_id)
            if article:
                article.embedding = vec
                session.add(article)
        except Exception as e:
            log(f"  Embed failed for #{art_id}: {e}")

    session.commit()


# ─── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Dead-man's-switch: did last night's run die silently? (best-effort)
    try:
        with Session(_engine) as session:
            check_liveness(session)
    except Exception as e:
        print(f"Liveness check failed: {e}", file=sys.stderr)

    stats = RunStats()
    crashed: Exception | None = None
    try:
        run_pipeline(stats)
    except Exception as e:
        crashed = e
        print(f"Pipeline failed: {e}", file=sys.stderr)

    stats.finish(ok=crashed is None)

    # Record stats + run the verifier. Best-effort: never flips the exit code.
    try:
        with Session(_engine) as session:
            record_run(session, stats)
            verify_run(session, stats)
    except Exception as e:
        print(f"Health recording/verify failed: {e}", file=sys.stderr)

    sys.exit(1 if crashed else 0)
