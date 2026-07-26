"""Find gaps in the controlled tag vocabulary — cheaply, without the LLM.

The idea: every article already carries a `potion-base-8M` embedding (see
`pipeline.embedding`). Each tag carries a "when to apply this" description we can
embed with the *same* model. So we can measure, in pure numpy, how well the
current vocabulary covers each article:

    coverage(article) = max cosine similarity to any tag vector

Articles whose best tag is far away are the ones the vocabulary can't describe —
candidates for a missing tag (e.g. text-to-speech, if no such tag exists). We
group those under-covered articles into clusters and print each cluster with a
few representative titles and its nearest existing tag, so a human can name the
gap and add it to `app/data/tags.json`.

No LLM calls: embeddings are already in the DB, tag vectors are one local encode
of ~30 tag strings, and clustering is greedy cosine math. Run it against prod by
pointing the POSTGRES_* env vars at prod (same vars the pipeline reads).

    cd backend && python -m scripts.find_missing_tags
    cd backend && python -m scripts.find_missing_tags --threshold 0.30 --json

Tune `--threshold` to what "poorly covered" means for your data: run once, look
at the coverage percentiles it prints, then set the threshold near the low tail.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from sqlmodel import Session, select

from app.models import Article, ArticleTag, Tag
from pipeline.db import get_engine
from pipeline.embedding import embed_batch


@dataclass
class ArticleVec:
    id: int
    title: str
    vec: np.ndarray  # L2-normalized
    tags: list[str] = field(default_factory=list)


def normalize(m: np.ndarray) -> np.ndarray:
    """L2-normalize rows; leave all-zero rows at zero (cosine -> 0)."""
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def tag_text(name: str, description: str | None) -> str:
    """The string we embed for a tag — the same signal the LLM tagger sees."""
    return f"{name}: {description}" if description else name


def load_tags(session: Session) -> tuple[list[str], list[str], np.ndarray]:
    """Return (slugs, names, normalized tag vectors), aligned by index."""
    rows = session.exec(select(Tag)).all()
    if not rows:
        sys.exit("tag table is empty — nothing to compare against")
    slugs = [t.slug for t in rows]
    names = [t.name for t in rows]
    vecs = embed_batch([tag_text(t.name, t.description) for t in rows])
    return slugs, names, normalize(np.asarray(vecs, dtype=np.float32))


def load_articles(
    session: Session, since: datetime | None, limit: int
) -> list[ArticleVec]:
    """Articles that have an embedding, with their assigned tag slugs attached."""
    stmt = select(Article).where(Article.embedding.is_not(None))  # type: ignore[union-attr]
    if since is not None:
        stmt = stmt.where(Article.published_at >= since)  # type: ignore[arg-type]
    stmt = stmt.order_by(Article.id)  # type: ignore[arg-type]
    if limit > 0:
        stmt = stmt.limit(limit)
    rows = session.exec(stmt).all()

    ids = [a.id for a in rows if a.id is not None]
    tags_by_article: dict[int, list[str]] = {i: [] for i in ids}
    if ids:
        pairs = session.exec(
            select(ArticleTag.article_id, Tag.slug)
            .join(Tag, Tag.id == ArticleTag.tag_id)  # type: ignore[arg-type]
            .where(ArticleTag.article_id.in_(ids))  # type: ignore[union-attr]
        ).all()
        for aid, slug in pairs:
            tags_by_article.setdefault(aid, []).append(slug)

    out: list[ArticleVec] = []
    for a in rows:
        if a.id is None or a.embedding is None:
            continue
        vec = np.asarray(a.embedding, dtype=np.float32)
        out.append(
            ArticleVec(id=a.id, title=a.title, vec=vec, tags=tags_by_article[a.id])
        )
    return out


@dataclass
class Cluster:
    centroid: np.ndarray  # normalized running mean
    members: list[int]  # indices into the under-covered list

    def add(self, idx: int, vec: np.ndarray) -> None:
        n = len(self.members)
        self.centroid = normalize(((self.centroid * n + vec) / (n + 1))[None, :])[0]
        self.members.append(idx)


def greedy_cluster(vecs: np.ndarray, sim_threshold: float) -> list[Cluster]:
    """One-pass greedy cosine clustering. Each vector joins the most similar
    existing cluster if it clears the threshold, else it seeds a new one.
    Good enough to surface coherent themes; not trying to be k-means."""
    clusters: list[Cluster] = []
    for i, v in enumerate(vecs):
        best_j, best_sim = -1, sim_threshold
        for j, c in enumerate(clusters):
            s = float(v @ c.centroid)
            if s >= best_sim:
                best_j, best_sim = j, s
        if best_j == -1:
            clusters.append(Cluster(centroid=v.copy(), members=[i]))
        else:
            clusters[best_j].add(i, v)
    return clusters


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--threshold",
        type=float,
        default=0.35,
        help="max-tag-similarity below this = under-covered (default 0.35)",
    )
    p.add_argument(
        "--cluster-sim",
        type=float,
        default=0.55,
        help="cosine similarity to merge under-covered articles (default 0.55)",
    )
    p.add_argument(
        "--min-cluster",
        type=int,
        default=3,
        help="only report clusters with at least this many articles (default 3)",
    )
    p.add_argument("--top", type=int, default=6, help="titles shown per cluster")
    p.add_argument(
        "--since",
        type=str,
        default=None,
        help="only articles published on/after this ISO date (e.g. 2026-01-01)",
    )
    p.add_argument("--limit", type=int, default=0, help="cap articles scanned (0=all)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = p.parse_args()

    since = datetime.fromisoformat(args.since) if args.since else None

    with Session(get_engine()) as session:
        slugs, names, tag_vecs = load_tags(session)
        articles = load_articles(session, since, args.limit)

    if not articles:
        sys.exit("no embedded articles found (is the DB seeded / embedded?)")

    A = normalize(np.stack([a.vec for a in articles]))
    sims = A @ tag_vecs.T  # (n_articles, n_tags)
    best_sim = sims.max(axis=1)
    best_tag = sims.argmax(axis=1)

    under_idx = np.where(best_sim < args.threshold)[0]
    under_vecs = A[under_idx]
    clusters = greedy_cluster(under_vecs, args.cluster_sim)
    clusters = [c for c in clusters if len(c.members) >= args.min_cluster]
    clusters.sort(key=lambda c: len(c.members), reverse=True)

    pct = np.percentile(best_sim, [5, 25, 50, 75, 95])
    stats = {
        "articles_scanned": len(articles),
        "under_covered": int(len(under_idx)),
        "under_covered_untagged": int(
            sum(1 for i in under_idx if not articles[i].tags)
        ),
        "threshold": args.threshold,
        "coverage_percentiles": {
            "p5": round(float(pct[0]), 3),
            "p25": round(float(pct[1]), 3),
            "p50": round(float(pct[2]), 3),
            "p75": round(float(pct[3]), 3),
            "p95": round(float(pct[4]), 3),
        },
    }

    report_clusters = []
    for c in clusters:
        member_articles = [articles[under_idx[m]] for m in c.members]
        member_local = np.stack([under_vecs[m] for m in c.members])
        order = (member_local @ c.centroid).argsort()[::-1]
        reps = [member_articles[o] for o in order[: args.top]]
        # Which existing tag is closest to this theme? Confirms it's a real gap
        # (low sim) and not a duplicate of something we already have (high sim).
        near = c.centroid @ tag_vecs.T
        nj = int(near.argmax())
        report_clusters.append(
            {
                "size": len(c.members),
                "nearest_existing_tag": slugs[nj],
                "nearest_tag_similarity": round(float(near[nj]), 3),
                "sample_titles": [r.title for r in reps],
            }
        )

    if args.json:
        print(json.dumps({"stats": stats, "candidate_gaps": report_clusters}, indent=2))
        return

    print("=== Tag coverage ===")
    print(f"Articles scanned:      {stats['articles_scanned']}")
    print(
        f"Under-covered (<{args.threshold}):  {stats['under_covered']} "
        f"({stats['under_covered_untagged']} of them have no tags at all)"
    )
    print(
        "Max-tag-similarity percentiles: "
        + "  ".join(f"{k}={v}" for k, v in stats["coverage_percentiles"].items())
    )
    print("(if p50 sits below your threshold, the threshold is too high)\n")

    if not report_clusters:
        print(
            "No candidate gaps at these settings. Lower --threshold or --min-cluster."
        )
        return

    print(
        f"=== {len(report_clusters)} candidate gap(s) — themes the vocabulary misses ===\n"
    )
    for i, rc in enumerate(report_clusters, 1):
        print(
            f"[{i}] {rc['size']} articles | nearest existing tag: "
            f"{rc['nearest_existing_tag']} (sim {rc['nearest_tag_similarity']})"
        )
        for t in rc["sample_titles"]:
            print(f"      - {t}")
        print()
    print(
        "Next: name each real gap and add it to app/data/tags.json, then "
        "re-run `python -m app.seed_tags`.\nBackfill tags on affected articles "
        "with the pipeline's assign_tags step."
    )


if __name__ == "__main__":
    main()
