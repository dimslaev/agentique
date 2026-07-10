class TitleFix {
  url string @description("The exact URL from the matching input article - copy verbatim")
  title string @description("Plain title text only. No surrounding quotes. No leading source name or bracket tag. Max 12 words. Return the input title verbatim if it is already clear, specific, and informative.")
}

function ImproveTitles(articles: ArticleInput[]) -> TitleFix[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a technical editor. You write clear, informative article titles for an AI developer news platform.

    Output rules (strict):
    - For each input article, return one TitleFix whose `url` exactly matches that article's URL.
    - The `title` field contains plain title text ONLY. Do NOT wrap it in quotes. Do NOT prefix it with "[Source]" or any source name. Do NOT include the URL.
    - Use only the snippet of the SAME article to inform the rewrite. Never blend information across articles.

    {{ _.role("user") }}
    Decide for each article whether the existing title is already good. A good title is specific, informative, and technical/neutral in register - it tells a developer what the article is actually about.

    - If the existing title is already good, return it verbatim.
    - Otherwise rewrite it using only that article's snippet: specific, informative, max 12 words, technical/neutral register, no hype or filler.

    {% for a in articles %}
    --- Article {{ loop.index }} ---
    url: {{ a.url }}
    source: {{ a.source }}
    current_title: {{ a.title }}
    {% if a.snippet %}snippet: {{ a.snippet }}{% endif %}
    {% endfor %}

    {{ ctx.output_format }}
  "#
}

test improve_titles_rewrite_short {
  functions [ImproveTitles]
  args {
    articles [
      {
        url "https://example.com/claude"
        title "Claude 4"
        source "HN"
        snippet "Anthropic today released Claude 4, a new flagship model with improved reasoning and a 1M-token context window."
      }
    ]
  }
}

test improve_titles_keep_unchanged {
  functions [ImproveTitles]
  args {
    articles [
      {
        url "https://example.com/post"
        title "Anthropic releases Claude 4 with 1M-token context window"
        source "HN"
        snippet "Anthropic today released Claude 4, a new flagship model with improved reasoning."
      }
    ]
  }
}
