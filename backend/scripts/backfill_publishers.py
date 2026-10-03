"""One-off: credit what the aggregators found to its authors, and give the
publishers the kinds the feed's "From" filter reads.

Run after migration fa1b2c3d4e5f, which saved each aggregator-credited
article's aggregator in `article.found_via` (the publisher column is about to
stop saying it). Writes as it goes and is safe to re-run: a row already moved
is no longer an aggregator's, and a publisher already made is found by its
link. Run it against a restored dump first and read the report.

    python scripts/backfill_publishers.py              # re-credit + lab kinds
    python scripts/backfill_publishers.py --export unknown.csv
    python scripts/backfill_publishers.py --kinds kinds.csv

`--export` writes the `unknown` publishers that have published articles, with
titles and summaries to judge them by. Fill in `kind` (lab, company,
individual, media) and optionally `name`, then apply it with `--kinds`.
Publishers with only rejects can stay `unknown`: the curation agent names one
the first time it approves its article.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from sqlmodel import Session, col, func, select

from app.catalog.models import (
    Article,
    ArticleKind,
    LinkPlatform,
    Publisher,
    PublisherKind,
)
from app.platform.db import engine
from pipeline.curation import NAMEABLE_KINDS
from pipeline.models import Reject
from pipeline.publishers import AGGREGATOR_TYPES, PublisherResolver

# Publishers that train and release their own models. Picked by hand from the
# 2026-10-03 publisher list.
LABS = {
    "Anthropic",
    "Answer.AI",
    "Apple ML Research",
    "Amazon Science",
    "Black Forest Labs",
    "Claude",
    "Cohere",
    "DeepSeek",
    "ElevenLabs",
    "Google AI Blog",
    "Google DeepMind Blog",
    "Google Research",
    "Liquid AI",
    "Meta AI",
    "Microsoft Research",
    "Mistral AI Blog",
    "Moonshot AI",
    "OpenAI Blog",
    "Runway",
    "Sakana AI",
    "Sarvam AI",
    "Stability AI",
    "xAI",
    "Xiaomi MiMo",
    "Zhipu AI",
}

# GitHub accounts that are a publisher we already carry, so their repos are
# credited to it rather than to a new publisher named after the account.
GITHUB_ACCOUNTS = {
    "Anthropic": "anthropics",
    "OpenAI Blog": "openai",
    "Google DeepMind Blog": "google-deepmind",
    "Meta AI": "facebookresearch",
    "Mistral AI Blog": "mistralai",
    "DeepSeek": "deepseek-ai",
    "Moonshot AI": "MoonshotAI",
    "Zhipu AI": "zai-org",
    "xAI": "xai-org",
    "Hugging Face Blog": "huggingface",
    "Microsoft Research": "microsoft",
    "NVIDIA Developer": "NVIDIA",
    "Cohere": "cohere-ai",
    "Ollama": "ollama",
    "Unsloth": "unslothai",
    "Vercel": "vercel",
    "Cloudflare": "cloudflare",
    "LlamaIndex": "run-llama",
    "Sakana AI": "SakanaAI",
}

EXPORT_TITLES = 3
EXPORT_SNIPPET = 300


def set_labs_and_accounts(session: Session) -> None:
    by_name = {p.name: p for p in session.exec(select(Publisher)).all()}
    missing = (LABS | GITHUB_ACCOUNTS.keys()) - by_name.keys()
    if missing:
        print(f"Not found, skipped: {', '.join(sorted(missing))}")
    for name in LABS & by_name.keys():
        by_name[name].kind = PublisherKind.lab
        session.add(by_name[name])
    for name, account in GITHUB_ACCOUNTS.items():
        if name in by_name:
            p = by_name[name]
            p.links = {**p.links, LinkPlatform.github: f"https://github.com/{account}"}
            session.add(p)
    session.commit()
    print(
        f"Labs: {len(LABS & by_name.keys())}, GitHub accounts: {len(GITHUB_ACCOUNTS)}"
    )


def recredit[T: (Article, Reject)](
    session: Session, resolver: PublisherResolver, model: type[T], aggregators: set[int]
) -> Counter[str]:
    """Move each row an aggregator is credited with to the publisher of the
    site its URL is on. A row on the aggregator's own site, or on a shared
    host that names no author, stays."""
    moved: Counter[str] = Counter()
    rows = session.exec(
        select(model).where(col(model.publisher_id).in_(aggregators))
    ).all()
    for row in rows:
        target = resolver.credit(row.url) or resolver.author(row.url)
        if target is None or target.id is None or target.id == row.publisher_id:
            continue
        row.publisher_id = target.id
        session.add(row)
        moved[target.name] += 1
    session.commit()
    print(f"{model.__name__}: {sum(moved.values())} of {len(rows)} moved")
    return moved


def export_unknown(session: Session, path: Path) -> None:
    """Only publishers with a published post: a repo, paper or model already
    has its tab whoever published it, so its publisher's kind can wait for
    the agent."""
    posts = select(Article.publisher_id).where(Article.kind == ArticleKind.post)
    publishers = session.exec(
        select(Publisher)
        .where(Publisher.kind == PublisherKind.unknown)
        .where(col(Publisher.id).in_(posts.distinct()))
        .order_by(Publisher.name)
    ).all()
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["site", "kind", "name", "articles", "evidence"])
        for p in publishers:
            articles = session.exec(
                select(Article)
                .where(Article.publisher_id == p.id)
                .order_by(col(Article.score).desc())
                .limit(EXPORT_TITLES)
            ).all()
            count = session.exec(
                select(func.count())
                .select_from(Article)
                .where(Article.publisher_id == p.id)
            ).one()
            evidence = " || ".join(
                f"{a.title} :: {(a.summary or '')[:EXPORT_SNIPPET]}" for a in articles
            )
            site = p.links.get(LinkPlatform.website, "")
            writer.writerow([site, "", "", count, evidence])
    print(f"Wrote {len(publishers)} unknown publishers to {path}")


def apply_kinds(session: Session, path: Path) -> None:
    """Keyed by the publisher's website link, not its slug: a slug made on a
    restored dump can differ from the one made on prod, the site cannot."""
    allowed = {k.value for k in NAMEABLE_KINDS}
    by_site = {
        p.links.get(LinkPlatform.website): p
        for p in session.exec(select(Publisher)).all()
        if p.kind == PublisherKind.unknown
    }
    updated = 0
    with path.open(newline="") as f:
        for line in csv.DictReader(f):
            kind = (line.get("kind") or "").strip().lower()
            if not kind:
                continue
            if kind not in allowed:
                raise SystemExit(
                    f"{line['site']}: kind {kind!r} is not one of {sorted(allowed)}"
                )
            p = by_site.get(line["site"])
            if p is None:
                print(f"No unknown publisher for {line['site']!r}, skipped")
                continue
            p.kind = PublisherKind(kind)
            if name := (line.get("name") or "").strip():
                p.name = name
            session.add(p)
            updated += 1
    session.commit()
    print(f"Set the kind of {updated} publishers")


def report(session: Session) -> None:
    rows = session.exec(
        select(Publisher.kind, Article.kind, func.count())
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .group_by(Publisher.kind, Article.kind)
        .order_by(Publisher.kind, Article.kind)
    ).all()
    print("\nArticles by publisher kind x article kind:")
    for pkind, akind, n in rows:
        print(f"  {pkind!s:<11} {akind!s:<6} {n}")


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--export", type=Path, help="write unknown publishers to this CSV"
    )
    parser.add_argument("--kinds", type=Path, help="apply kinds from this CSV")
    args = parser.parse_args()

    with Session(engine) as session:
        if args.export:
            export_unknown(session, args.export)
            return
        if args.kinds:
            apply_kinds(session, args.kinds)
            report(session)
            return

        set_labs_and_accounts(session)
        aggregators = {
            p.id
            for p in session.exec(select(Publisher)).all()
            if p.type in AGGREGATOR_TYPES and p.id is not None
        }
        resolver = PublisherResolver(session)
        moved = recredit(session, resolver, Article, aggregators)
        recredit(session, resolver, Reject, aggregators)
        print(f"\n{len(resolver.created)} publishers created")
        print("Articles moved, by new publisher (top 40):")
        for name, n in moved.most_common(40):
            print(f"  {n:>4}  {name}")
        report(session)


if __name__ == "__main__":
    main()
