class ExtractedLink {
  title string
  url string
  snippet string @description("One-sentence description of the article")
}

function ExtractLinks(emailHtml: string) -> ExtractedLink[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a precise link extraction engine. You parse newsletter HTML and identify external article links while filtering out tracking, admin, and promotional URLs.

    {{ _.role("user") }}
    You are given the HTML body of a newsletter email. Extract all article links that point to external news stories, blog posts, research papers, or product announcements.

    For each article, return its title, URL, and a one-sentence snippet describing it.

    IGNORE these types of links:
    - Tracking/redirect URLs (e.g. links through email marketing platforms)
    - Unsubscribe, manage preferences, or email settings links
    - Social media profile links (twitter, linkedin, etc.)
    - Links back to the newsletter's own homepage, archive index, or subscription page (but DO include article/post links hosted on the newsletter's domain - curated newsletters often host their own content)
    - Sponsor/advertisement links
    - Job posting links

    RESOLVE redirect URLs: if a link is clearly a tracking redirect (contains /click, /track, utm_ params, etc.), try to extract the final destination URL from the href. Strip all UTM parameters from URLs.

    Newsletter HTML:
    {{ emailHtml }}

    If no relevant article links are found, return an empty list.

    {{ ctx.output_format }}
  "#
}

test extract_links_basic {
  functions [ExtractLinks]
  args {
    emailHtml "Welcome to today's issue! [Read OpenAI's new paper](https://openai.com/papers/gpt-5). [Unsubscribe](https://newsletter.com/unsubscribe)."
  }
}
