"""One-off: add the tools a GitHub search found, judged by a model that reads
one prompt and calls no tools.

    python -m app.entry.cli.backfill_tools next tools.json -n 30 > batch.txt
    python -m app.entry.cli.backfill_tools apply tools.json verdicts.jsonl

`next` prints the whole prompt for the next tools nothing has judged yet:
rubric, tag vocabulary, and each repo with the start of its README. `apply`
queues the judged repos and approves or rejects each through the curation
verbs, so publishers, tags, embeddings and the ledger are written the usual
way. A judged URL is known from then on, which is what makes the loop
(`scripts/backfill-tools.sh`) stateless.

`tools.json` is a list of `{n: "owner/repo", s: stars, c: created, d:
description, topics: [...]}`, built by paging GitHub's repository search.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from pathlib import Path
from typing import TypedDict

from sqlmodel import Session

from app.core.db.article import Article
from app.core.db.engine import engine
from app.core.http import fetch_with_timeout
from app.features.collect.model import Candidate, RawItem
from app.features.collect.service import PublisherResolver, filter_known_urls
from app.features.collect.service import queue_candidates as queue
from app.features.curation import service as curation
from app.features.curation.model import CandidateError

README_CHARS = 2500
KEEP_SCORE = 70
# Badges, images and raw HTML open most READMEs and say nothing.
NOISE = re.compile(r"^\s*(<|\[!\[|!\[).*$", re.MULTILINE)

RUBRIC = """\
You judge GitHub repos for agentique, a curated feed for developers building
with AI. Each repo below has its stars, topics, description and the start of
its README. Output one JSON object per repo, one per line, nothing else:

{"repo": "owner/name", "keep": true, "score": 78, "reason": "...",
 "title": "...", "summary": "...", "tags": ["..."], "publisher_kind": "...",
 "publisher_name": "..."}

keep: true when a developer building with AI can use this repo today. false for
out of scope (crypto, non-AI tools, job-search or marketing bots, courses,
awesome-lists, prompt dumps, leaked system prompts, free-API-key proxies) and
for repos whose README shows nothing concrete.

score: 80-89 real technical substance, usable today; 70-79 useful but narrow or
modest novelty; 55-69 minor tools and demos; 35-54 unverified claims, marketing
pages; 15-34 slop; 1-14 out of scope only. Stars are reach evidence, not
quality. keep is true only at 70 or above.

reason: one sentence naming what decided it.

title (keep only): the tool's name as its README writes it, then " - " and what
it is in under 8 plain words.

summary (keep only): one hook line saying what it is, then 2-4 lines starting
with "- " giving what the README actually shows. No marketing adjectives. Only
what the README supports. Use \\n between lines.

tags (keep only): up to 3 slugs from the list below, only where the description
fits the repo's subject. Add a lab tag on top when the repo is built on that
lab's product.

publisher_kind: who owns the account, one of lab, company, individual, media.
publisher_name: how a reader should see the owner when the account name does
not read well, else omit.
"""


class Tool(TypedDict):
    n: str
    s: int
    c: str
    d: str
    topics: list[str]


class Verdict(TypedDict, total=False):
    repo: str
    keep: bool
    score: int
    reason: str
    title: str
    summary: str
    tags: list[str]
    publisher_kind: str
    publisher_name: str


def _url(tool: Tool) -> str:
    return f"https://github.com/{tool['n']}"


def _readme(repo: str) -> str:
    """The README's text, empty when it is not at the usual path."""
    try:
        resp = fetch_with_timeout(
            f"https://raw.githubusercontent.com/{repo}/HEAD/README.md", timeout=10.0
        )
    except Exception:
        return ""
    return NOISE.sub("", resp.text).strip() if resp.status_code == 200 else ""


def _item(tool: Tool) -> RawItem:
    return {
        "title": tool["n"].partition("/")[2],
        "url": _url(tool),
        "content": f"{tool['d']}\n\n{_readme(tool['n'])}",
        "published_date": tool["c"],
        "source": "GitHub",
        "traction": f"{tool['s']} stars",
    }


def _load(path: Path) -> list[Tool]:
    tools: list[Tool] = json.loads(path.read_text())
    return tools


def next_batch(session: Session, tools: list[Tool], n: int) -> str:
    """The prompt for the next ``n`` tools no article or ledger row covers,
    empty when none are left."""
    stubs: list[RawItem] = [
        {
            "title": t["n"],
            "url": _url(t),
            "content": "",
            "published_date": None,
            "source": "GitHub",
        }
        for t in tools
    ]
    fresh = {a["url"] for a in filter_known_urls(session, stubs, "backfill")}
    batch = [t for t in tools if _url(t) in fresh][:n]
    if not batch:
        return ""

    vocab = curation.vocabulary(session)["tags"]
    assert isinstance(vocab, dict)
    tags = "\n".join(f"{slug}: {desc}" for slug, desc in vocab.items())
    repos = "\n\n".join(
        f"### {t['n']} | {t['s']} stars | created {t['c']} | topics: "
        f"{', '.join(t['topics'])}\n{t['d']}\n\n{_readme(t['n'])[:README_CHARS]}"
        for t in batch
    )
    return f"{RUBRIC}\n## Tags\n{tags}\n\n## Repos\n\n{repos}\n"


def apply(session: Session, tools: list[Tool], verdicts: list[Verdict]) -> None:
    by_name = {t["n"].lower(): t for t in tools}
    resolver = PublisherResolver(session)
    approved = rejected = 0
    for v in verdicts:
        tool = by_name.get(v.get("repo", "").lower())
        if tool is None:
            print(f"skip {v.get('repo')}: not in the list")
            continue
        item = _item(tool)
        item["title"] = v.get("title") or item["title"]
        if not filter_known_urls(session, [item], "backfill"):
            continue
        publisher = resolver.credit(item["url"]) or resolver.author(item["url"])
        if publisher is None or publisher.id is None:
            print(f"skip {tool['n']}: no publisher")
            continue
        candidate: Candidate = {**item, "publisher_id": publisher.id}
        queue(session, [candidate])
        try:
            # The model sometimes says keep on a score its own rubric rejects.
            if v.get("keep") and v["score"] >= KEEP_SCORE:
                article_id = curation.approve(
                    session,
                    item["url"],
                    v["score"],
                    v["reason"],
                    v["summary"],
                    "repo",
                    v.get("tags", []),
                    v.get("publisher_kind"),
                    v.get("publisher_name"),
                )
                # The newsletter and the daily mail read `created_at` as "new
                # this week"; a backfilled tool is not.
                article = session.get(Article, article_id)
                if article and article.published_at:
                    article.created_at = article.published_at
                    session.commit()
                approved += 1
            else:
                curation.reject(session, item["url"], v["score"], v["reason"])
                rejected += 1
        except (CandidateError, KeyError) as exc:
            # The row stays pending, so the nightly agent sees it.
            print(f"left pending {tool['n']}: {exc!r}")
    print(f"approved {approved}, rejected {rejected}")


def _verdicts(path: Path) -> list[Verdict]:
    """One per line that parses as an object; a model's stray prose is not one."""
    out: list[Verdict] = []
    for line in path.read_text().splitlines():
        if line.strip().startswith("{"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"unreadable verdict: {line[:80]}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    nxt = sub.add_parser("next")
    nxt.add_argument("tools", type=Path)
    nxt.add_argument("-n", type=int, default=30)
    app = sub.add_parser("apply")
    app.add_argument("tools", type=Path)
    app.add_argument("verdicts", type=Path)
    args = parser.parse_args()

    with Session(engine) as session:
        if args.command == "next":
            # The collect verbs log to stdout, which here is the prompt.
            with contextlib.redirect_stdout(sys.stderr):
                prompt = next_batch(session, _load(args.tools), args.n)
            sys.stdout.write(prompt)
        else:
            apply(session, _load(args.tools), _verdicts(args.verdicts))


if __name__ == "__main__":
    main()
