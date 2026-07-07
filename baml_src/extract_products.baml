// Product-centric newsletter extraction.
//
// Replaces the per-newsletter tracking-URL resolvers: instead of decoding each
// provider's redirect scheme to recover the real link, we extract the *named
// products* a newsletter reports on (from anchor text + surrounding prose),
// keep only the notable ones, and rediscover their canonical URLs via web
// search (src/sources/email.ts). SelectProductLink then picks the best
// first-party result among the candidates.

class NewsletterProduct {
  name string @description("Exact product / tool / model / launch name")
  description string @description("Concise phrase: what it is and does, usable verbatim as a web search query")
}

function ExtractProducts(newsletterText: string) -> NewsletterProduct[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You extract the AI/tech products, tools, models, and launches that a newsletter is reporting on. Work only from the text; never invent products that are not mentioned.

    {{ _.role("user") }}
    Below is the text of a newsletter email. Links appear as [anchor text](url) but the URLs are often tracking redirects, so judge by the words, not the links.

    Identify every distinct product, tool, model, SDK, dataset, or launch the newsletter is reporting as news. For each, return:
    - name: the exact product/tool/model name
    - description: a concise phrase describing what it is and does, suitable as a web search query

    INCLUDE only real, named launches a reader could go use or read about.

    IGNORE:
    - the author's intro letter, essay, or personal commentary
    - sponsor blurbs, advertisements, "brought to you by", upgrade / subscribe / manage-preferences prompts
    - social-media embeds (an @handle with like / repost / reply counts) and the newsletter's own social links
    - section headers, navigation, and unsubscribe links

    Newsletter text:
    {{ newsletterText }}

    If the text names no qualifying products, return an empty list.

    {{ ctx.output_format }}
  "#
}

// Notability gate: trims the extracted list to the launches actually worth
// resolving, so we don't spend a web search on every incremental SDK bump.
// Returns the 1-based indices of the products to KEEP.
function SelectNotableProducts(products: NewsletterProduct[]) -> int[] {
  client Nvidia
  prompt #"
    {{ _.role("user") }}
    Below is a numbered list of products/tools/models a newsletter mentioned. Return the numbers of the ones that are NOTABLE enough to feature in an AI-news aggregator.

    KEEP a product if it is a distinct, real, individually newsworthy launch a reader would want to click: new models, significant new products or platforms, notable agents/tools, major releases.

    DROP:
    - minor or incremental items: small SDK/utility bumps, niche helper libraries, design skills, config tweaks
    - vague or marketing-only entries with no concrete product behind them
    - duplicates or sub-features of another item in the list

    Products:
    {% for p in products %}
    {{ loop.index }}. {{ p.name }} — {{ p.description }}
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

test extract_products_basic {
  functions [ExtractProducts]
  args {
    newsletterText "Headlines: [OpenAI ships GPT-5](https://sub.stack/redirect/2/abc), a new flagship model. Brought to you by Acme. [Unsubscribe](https://newsletter.com/unsub)."
  }
}
