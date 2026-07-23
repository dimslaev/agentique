class SummarizeAndCategorizeResult {
  summary string @description("2-3 short factual lines of plain English, separated by \\n. No markdown, no other language.")
  categories ArticleCategory[] @description("1-2 categories")
  kind ArticleKind
}

class ClassifyKindResult {
  kind ArticleKind
}

function SummarizeAndCategorize(title: string, content: string) -> SummarizeAndCategorizeResult {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a technical writer for a developer news digest. Your readers are tech-savvy but busy. Write in plain, direct language.

    {{ _.role("user") }}
    Summarize this article. Be plain and brief.

    Title: {{ title }}

    Content:
    {{ content }}

    1. Write 2-3 lines. Keep each line to one short sentence. Rules:
       - Only state facts from the article.
       - No passive voice. No "enables", "allows", "provides".
       - Separate lines with a newline.
       - Write in English. Never emit any other language or script, even if the
         source content contains one.
       - Plain text only. The source is often markdown - do NOT copy its
         formatting. No **bold**, no backticks, no headings, no bullets.
       - Never truncate mid-word or mid-sentence.
    2. Assign 1-2 categories.
    3. Assign a kind.

    Category definitions:
    - Models: New model releases, benchmarks, evals, model cards, model comparisons
    - Dev: Repos, tools, product launches, developer blogs, tutorials, how-tos, fine-tuning guides, deployment recipes, infrastructure updates
    - Research: Papers, breakthroughs, novel techniques with practical implications

    Kind definitions:
    - Repo: GitHub or GitLab repository
    - Paper: Academic paper, preprint, or long-form technical report
    - Model: Model card or model release page (e.g. HuggingFace)
    - Blog: Developer blog post, tutorial, how-to, or opinion piece
    - Product: Product launch page or product website
    - Announcement: Official release post from a major AI lab (OpenAI, Anthropic, Google, Meta, Mistral, etc.)

    {{ ctx.output_format }}
  "#
}

function ClassifyKind(title: string, url: string, summary: string?) -> ClassifyKindResult {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a technical librarian who classifies AI developer content by format.

    {{ _.role("user") }}
    Classify this article's kind.

    Title: {{ title }}
    URL: {{ url }}
    {% if summary %}Summary: {{ summary }}{% endif %}

    Kind definitions:
    - Repo: GitHub or GitLab repository
    - Paper: Academic paper, preprint, or long-form technical report
    - Model: Model card or model release page (e.g. HuggingFace)
    - Blog: Developer blog post, tutorial, how-to, or opinion piece
    - Product: Product launch page or product website
    - Announcement: Official release post from a major AI lab (OpenAI, Anthropic, Google, Meta, Mistral, etc.)

    {{ ctx.output_format }}
  "#
}

test summarize_basic {
  functions [SummarizeAndCategorize]
  args {
    title "Anthropic releases Claude 4"
    content "Anthropic today launched Claude 4, a new flagship model. It features improved reasoning, a 1M-token context window, and native tool use. The model is available via API and Claude.ai starting today."
  }
}

test categorize_only_basic {
  functions [CategorizeOnly]
  args {
    title "OpenAI releases GPT-5 with 2M context"
  }
}

// ─── Regression tests ───────────────────────────────────────────────────────
// Summarize is where the corruption starts: it wrote summaries containing
// **bold** and stray CJK into prod, and ImproveTitles then copied them into
// titles. Source content is usually markdown (READMEs, newsletters), so the
// model echoing its formatting is the likely mechanism.
//
// Run: cd baml_src && baml-cli test

test regression_markdown_source_not_echoed {
  functions [SummarizeAndCategorize]
  args {
    title "sqlsure: deterministic SQL validation"
    content #"
      # sqlsure

      **sqlsure** detects hidden logical errors in AI-written SQL *before* execution, in ~0.1ms.

      ## How it works
      - Uses team-declared schema rules (e.g. `dbt` tests)
      - Validates `JOIN`s, aggregates, and logical flaws
      - Catches revenue double-counting and exposed data

      ```sql
      SELECT * FROM orders JOIN users USING (user_id);
      ```
    "#
  }
  @@assert(no_bold, {{ "**" not in this.summary }})
  @@assert(no_backticks, {{ "`" not in this.summary }})
  @@assert(no_heading, {{ "#" not in this.summary }})
  @@assert(non_empty, {{ this.summary|length > 20 }})
}

test regression_cjk_source_not_echoed {
  functions [SummarizeAndCategorize]
  args {
    title "Meta sizes up GPT-5.5 with Watermelon"
    content #"
      Meta shares details on Watermelon, an internal GPT-5.5 benchmarking framework
      for ML experiments. 伊律(Meagle) 这是一个内部实验框架。
      Frameworks like this test scalability, efficiency, and performance of large models.
    "#
  }
  @@assert(no_cjk, {{ "伊" not in this.summary and "这" not in this.summary and "框" not in this.summary }})
  @@assert(no_bold, {{ "**" not in this.summary }})
  @@assert(non_empty, {{ this.summary|length > 20 }})
}

test regression_summary_stays_short {
  functions [SummarizeAndCategorize]
  args {
    title "OpenAI Build Week"
    content #"
      SF developers can get live help and structured testing for frontier GPT-5.6 systems.
      Local workshops guide them from concept to implementation over the course of a week.
      The event offers hands-on access to AI system trials, with sessions on agent design,
      evaluation harnesses, and deployment. Registration is open to all developers.
    "#
  }
  @@assert(no_json, {{ "}" not in this.summary and "]" not in this.summary and "{" not in this.summary }})
  @@assert(bounded, {{ this.summary|length < 1000 }})
  @@assert(non_empty, {{ this.summary|length > 20 }})
}
