// Newsletter extraction.
//
// A newsletter reports two kinds of thing worth ingesting, and they need
// different URL resolution:
//
// - Product: a named launch (model, tool, SDK). Its canonical URL is the
//   vendor's own page, which the email rarely links to directly, so the URL is
//   rediscovered by web search (SelectProductLink) rather than trusted from the
//   email. This replaced the per-newsletter tracking-URL decoders.
// - Article: a blog post, essay, paper, or write-up. Here the link IS the
//   subject — there is nothing to search for, and a search would land on some
//   other page about the same topic. Its href is kept and followed instead
//   (see ``_resolve_article`` in pipeline/sources/email.py), which turns a
//   tracking redirect into the real destination.
//
// Hence NewsletterItem.url: the model must copy an article's href verbatim
// even though it is usually a redirect, because following it is exactly how
// the real URL is recovered.

enum NewsletterItemKind {
  Product  // A named product, tool, model, SDK, dataset, or launch
  Article  // A blog post, essay, paper, guide, or write-up
}

class NewsletterItem {
  kind NewsletterItemKind
  name string @description("Product name, or the article's title")
  description string @description("Concise phrase: what it is and does, usable verbatim as a web search query")
  url string? @description("For an Article, the href of its link, copied verbatim including any tracking redirect. Omit for a Product.")
}

function ExtractItems(newsletterText: string) -> NewsletterItem[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You extract the AI/tech items a newsletter is reporting on: named products, and the articles it links to. Work only from the text; never invent items that are not mentioned.

    {{ _.role("user") }}
    Below is the text of a newsletter email. Links appear as [anchor text](url).

    Identify every distinct item the newsletter reports as news, and classify each:

    - Product — a named product, tool, model, SDK, dataset, or launch a reader could go use. Judge it by the words, not the link: its URL is looked up separately, so do NOT return a url for a Product.
    - Article — a blog post, essay, paper, guide, benchmark write-up, or analysis the newsletter is pointing at. For these the link is the subject, so ALWAYS return its url, copied verbatim from the text — including tracking redirects, which are followed later to recover the real destination. An item with no link is not an Article.

    For each item return:
    - kind: Product or Article
    - name: the exact product name, or the article's title
    - description: a concise phrase describing what it is and does, suitable as a web search query
    - url: the article's href (Article only)

    A single story often yields one item, not two: if a link is the vendor's own announcement of a named launch, return it as a Product. Return an Article when the piece itself is the point — someone's write-up, teardown, guide, or opinion.

    INCLUDE only real, named launches and substantive articles a reader could go use or read.

    IGNORE:
    - the author's intro letter and personal commentary
    - sponsor blurbs, advertisements, "brought to you by", upgrade / subscribe / manage-preferences prompts
    - social-media embeds (an @handle with like / repost / reply counts) and the newsletter's own social links
    - section headers, navigation, and unsubscribe links
    - job postings

    Newsletter text:
    {{ newsletterText }}

    If the text names no qualifying items, return an empty list.

    {{ ctx.output_format }}
  "#
}

// Notability gate: trims the extracted list to the items actually worth
// resolving, so we don't spend a web search on every incremental SDK bump.
// Returns the 1-based indices of the items to KEEP.
function SelectNotableItems(items: NewsletterItem[]) -> int[] {
  client Nvidia
  prompt #"
    {{ _.role("user") }}
    Below is a numbered list of items a newsletter mentioned. Return the numbers of the ones that are NOTABLE enough to feature in an AI-news aggregator.

    KEEP an item if it is distinct, real, and individually newsworthy: new models, significant new products or platforms, notable agents/tools, major releases, and articles with real substance — technical write-ups, benchmarks, teardowns, engineering posts, or arguments a developer would want to read.

    DROP:
    - minor or incremental items: small SDK/utility bumps, niche helper libraries, design skills, config tweaks
    - vague or marketing-only entries with no concrete product behind them
    - listicles, SEO filler, press-release rewrites, and thin news blurbs that only restate an announcement
    - duplicates or sub-features of another item in the list

    Items:
    {% for item in items %}
    {{ loop.index }}. [{{ item.kind }}] {{ item.name }} — {{ item.description }}
    {% endfor %}

    Return only the numbers to keep, as a JSON array of integers. If none qualify, return [].

    {{ ctx.output_format }}
  "#
}

class SearchCandidate {
  title string
  url string
  snippet string
}

class ProductLinkChoice {
  index int @description("1-based index of the best first-party result, or 0 if none qualifies")
  confidence float @description("0.0 - 1.0")
}

// Picks the best canonical URL for a product among search candidates, biased
// hard toward the official / first-party source and away from social posts and
// SEO/aggregator pages. Returns index 0 when nothing is clearly the product.
// Products only — an article already carries its own link.
function SelectProductLink(
  productName: string,
  productDescription: string,
  candidates: SearchCandidate[]
) -> ProductLinkChoice {
  client Nvidia
  prompt #"
    {{ _.role("user") }}
    A newsletter featured this item:
      name: {{ productName }}
      description: {{ productDescription }}

    Web search returned these candidate results:
    {% for c in candidates %}
    {{ loop.index }}. {{ c.title }}
       url: {{ c.url }}
       snippet: {{ c.snippet }}
    {% endfor %}

    Pick the ONE candidate that is the canonical, first-party source for this exact product — its official site, product page, model card, repo, or the vendor's own announcement.

    PREFER the official / first-party domain that matches the product or its maker.
    REJECT (do not pick) when it is the best available:
    - social-media posts (x.com, twitter.com, linkedin.com, reddit.com, threads, mastodon)
    - videos (youtube.com)
    - content-farm / SEO / generic aggregator or listicle pages that merely mention the product
    - a DIFFERENT product that happens to share the name

    Return the 1-based index of the best first-party result. If none of the candidates is clearly a first-party source for THIS product, return index 0.

    {{ ctx.output_format }}
  "#
}

test extract_items_basic {
  functions [ExtractItems]
  args {
    newsletterText "Headlines: [OpenAI ships GPT-5](https://sub.stack/redirect/2/abc), a new flagship model. Deep dive: [Why agent harnesses fail](https://stencil.so/blog/harness-playbook?utm_source=tldrai) walks through production agent design. Brought to you by Acme. [Unsubscribe](https://newsletter.com/unsub)."
  }
}
