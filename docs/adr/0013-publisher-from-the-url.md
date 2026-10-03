# 13. The publisher comes from the URL; the aggregator is how it was found

## Status

Accepted.

## Context

The feed had two filter rows nobody used. Category (`models`, `dev`,
`research`) did not split the feed: `dev` was on 70% of it. Kind mixed what an
article is (`repo`, `paper`, `model`) with a guess at what sort of post it was
(`blog`, `product`, `announcement`), and the agent made that guess differently
night to night: a Cursor launch was a `product`, a Cloudflare launch an
`announcement`, a Simon Willison post an `announcement`.

What a reader picks by is who wrote it: a lab, a company, a person, a news
outlet. `PublisherKind` already said that, but it could not be trusted. A link
Hacker News or a newsletter found was credited to the aggregator unless the
site was one we already carried, so on 2026-10-03 592 of 1212 articles (48%)
were Hacker News's, TLDR AI's or another aggregator's: personal blogs, repos,
lab announcements on hosts we had no alias for (`claude.com` for Anthropic).

## Decision

- **An aggregator is never a link's publisher.** `PublisherResolver.publisher_for`
  credits a link from an aggregator source (`hn`, `email`, `ainews`, `reddit`)
  to the site it is on. A site we do not carry gets a publisher on the spot:
  inactive, with only a `website` link, so it is never polled. On GitHub, Hugging
  Face and Medium the account in the path is the publisher
  (`github.com/mattpocock`), and a publisher's own `github` link claims its
  account's repos. A shared host that names no author (a tweet, a Reddit
  thread) stays with the aggregator. A feed's own items stay with the feed.
- **The aggregator is kept as `Article.found_via`.** The migration filled it
  for every aggregator-credited article before the backfill moved them.
- **A new publisher's kind is `unknown` until the curation agent names it.**
  A GitHub or Hugging Face user, a `*.github.io` or a Substack is `individual`
  from the URL; everything else needs reading. `approve` refuses an `unknown`
  publisher without `publisher_kind`, and never changes a kind once set.
- **`PublisherKind` gains `lab`**: makes models and writes about them on its own
  site, apart from companies whose blogs are mostly product posts and
  tutorials. Set by hand on 25 publishers.
- **`ArticleKind` is `post`, `repo`, `paper`, `model`.** `blog`, `product` and
  `announcement` fold into `post`; who published it says the rest.
- **One "From" row replaces Category and Kind**: Labs, Companies, Writers,
  Media, Repos, Papers, Models. A repo, paper or model is that whoever published
  it; a post falls under its publisher's kind (`community` under Media).
  `origin` on the articles API applies the rule server-side.
- **Category is no longer written or served.** The column stays.

## Consequences

The pipeline makes publishers on its own now, hundreds at first: the backfill
made 670 for 2026-10-03's data, most of them for rejects. They are inactive
rows, not sources. Promoting one that keeps getting approved to a feed is a
hand step: add its RSS link and set it active.

A post whose publisher is still `unknown` is under All and under no tab until
its kind is set: by the agent on the publisher's next approval, or by hand for
the backlog (`scripts/backfill_publishers.py --export` / `--kinds`).

A lab's Hugging Face org (`huggingface.co/deepseek-ai`) is a publisher apart
from the lab's own, since a publisher has one `github` link and no Hugging Face
one. Merging such duplicates is by hand.

Owner lookups use the unauthenticated GitHub API (60 an hour). A failed lookup
leaves the owner `unknown` rather than guessing, so a rate limit costs the
agent a question, not a wrong label.
