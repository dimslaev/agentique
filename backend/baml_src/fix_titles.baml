class TitleFix {
  url string @description("The exact URL from the matching input article - copy verbatim")
  title string @description("Plain English title text on a single line. No markdown, no quotes, no leading source name or bracket tag. Max 12 words. Return the input title verbatim if it is already clear, specific, and informative.")
}

function ImproveTitles(articles: ArticleInput[]) -> TitleFix[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a technical editor. You write clear, informative article titles for an AI developer news platform.

    Output rules (strict):
    - For each input article, return one TitleFix whose `url` exactly matches that article's URL.
    - The `title` field contains plain title text ONLY. Do NOT wrap it in quotes. Do NOT prefix it with "[Source]" or any source name. Do NOT include the URL.
    - Write in English. Never emit any other language or script.
    - No markdown. Do NOT wrap the title in ** or * or _ or backticks.
    - One single line. No newlines, no braces, no brackets, no JSON.
    - Every title must be a complete phrase. Never truncate mid-word or mid-sentence.
    - Use only the snippet of the SAME article to inform the rewrite. Never blend information across articles.

    {{ _.role("user") }}
    Decide for each article whether the existing title is already good. A good title is specific, informative, and technical/neutral in register - it tells a developer what the article is actually about.

    - If the existing title is already good, return it verbatim.
    - Otherwise rewrite it using only that article's snippet: specific, informative, between 3 and 12 words, technical/neutral register, no hype or filler.
    - If the snippet is empty or too thin to write an accurate title from, return the existing title verbatim rather than inventing one.

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

// ─── Regression tests ───────────────────────────────────────────────────────
// Real inputs from the production `article` table that produced corrupted
// titles. Note the snippets are themselves already dirty (markdown bold,
// stray CJK) — Summarize emitted them, and ImproveTitles copied the garbage
// straight into the title. These assert the model no longer propagates it.
//
// Run: cd baml_src && baml-cli test

test regression_cjk_in_snippet {
  functions [ImproveTitles]
  args {
    articles [
      {
        url "https://x.com/TeksCreate/status/2075315553602814410"
        title "GPT-5.6 agent workflows"
        source "Aligned News"
        snippet #"
          GPT-5.6 focuses on supporting autonomous agents that operate for hours.
          伊律(Meagle) this highlights durable workflows over raw benchmark score increases.
          OpenAI had not previously publicized its agent capabilities as a key feature before now.
        "#
      }
    ]
  }
  @@assert(url_preserved, {{ this[0].url == "https://x.com/TeksCreate/status/2075315553602814410" }})
  @@assert(no_markdown, {{ "**" not in this[0].title }})
  @@assert(no_cjk, {{ "伊" not in this[0].title and "律" not in this[0].title }})
  @@assert(single_line, {{ "\n" not in this[0].title }})
  @@assert(max_12_words, {{ this[0].title|split(" ")|list|length <= 12 }})
}

test regression_markdown_in_snippet {
  functions [ImproveTitles]
  args {
    articles [
      {
        url "https://www.therundown.ai/p/meta-sizes-up-gpt-5-5-with-watermelon"
        title "Meta sizes up GPT-5.5 with Watermelon"
        source "The Rundown AI"
        snippet #"
          Meta shares details on **Watermelon**, an internal GPT-5.5 benchmarking framework for ML experiments.
          Frameworks like this test scalability, efficiency, and performance of large models.
          Cursor Mobile also extends screenshot-to-bug-fix workflows for developers.
        "#
      }
    ]
  }
  @@assert(no_markdown, {{ "**" not in this[0].title and "*" not in this[0].title }})
  @@assert(single_line, {{ "\n" not in this[0].title }})
  @@assert(no_json, {{ "}" not in this[0].title and "]" not in this[0].title }})
  @@assert(max_12_words, {{ this[0].title|split(" ")|list|length <= 12 }})
}

// Produced the truncated `**"GPT-5.6` title in prod.
test regression_truncated_generation {
  functions [ImproveTitles]
  args {
    articles [
      {
        url "https://www.bensbites.com/p/grok-x-cursor"
        title "Grok x Cursor"
        source "Ben's Bites"
        snippet #"
          OpenAI updated ChatGPT with GPT-5.6 and a synthetic voice feature.
          The changes include the ability to swap between voices in the free tier.
          A new preview mode called 'Fable' introduces narrative-based interactions.
        "#
      }
    ]
  }
  @@assert(no_quote_wrapper, {{ '"' not in this[0].title }})
  @@assert(no_markdown, {{ "**" not in this[0].title }})
  @@assert(complete_phrase, {{ this[0].title|split(" ")|list|length >= 3 }})
  @@assert(max_12_words, {{ this[0].title|split(" ")|list|length <= 12 }})
}

// Produced the title with raw JSON (`}` / `]`) welded onto the end.
test regression_json_envelope_leak {
  functions [ImproveTitles]
  args {
    articles [
      {
        url "https://openai.com"
        title "Build Week"
        source "Aligned News"
        snippet #"
          SF developers can get live help and structured testing for frontier GPT-5.6 systems.
          Local workshops guide them from concept to implementation.
          The event offers hands-on access to AI system trials.
        "#
      }
    ]
  }
  @@assert(no_json, {{ "}" not in this[0].title and "]" not in this[0].title and "{" not in this[0].title }})
  @@assert(single_line, {{ "\n" not in this[0].title }})
  @@assert(max_12_words, {{ this[0].title|split(" ")|list|length <= 12 }})
}

// Thin snippet: the model must fall back to the original title, not invent one.
test regression_thin_snippet_keeps_original {
  functions [ImproveTitles]
  args {
    articles [
      {
        url "https://example.com/thin"
        title "Anthropic ships Claude Code updates"
        source "HN"
        snippet "Read more."
      }
    ]
  }
  @@assert(kept_original, {{ this[0].title == "Anthropic ships Claude Code updates" }})
}

// Batch: URLs must not get crossed and content must not blend across articles.
test regression_batch_no_crosstalk {
  functions [ImproveTitles]
  args {
    articles [
      {
        url "https://example.com/a"
        title "Meta releases Muse image model"
        source "HN"
        snippet "Meta made its Muse image model free on Instagram and WhatsApp, with API access."
      }
      {
        url "https://example.com/b"
        title "vLLM news"
        source "HN"
        snippet "vLLM now integrates Hugging Face Transformers for production-grade inference serving."
      }
    ]
  }
  @@assert(both_returned, {{ this|list|length == 2 }})
  @@assert(urls_distinct, {{ this[0].url != this[1].url }})
  @@assert(no_blend, {{ "Muse" not in this[1].title }})
}
