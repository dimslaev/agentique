class TagOption {
  slug string
  description string? @description("When to apply this tag")
}

class CategorizeAndTagResult {
  categories ArticleCategory[] @description("1-2 categories")
  kind ArticleKind
  tags string[] @description("1-3 slugs copied verbatim from the vocabulary; most relevant first")
}

class ClassifyKindResult {
  kind ArticleKind
}

function CategorizeAndTag(title: string, content: string, vocabulary: TagOption[]) -> CategorizeAndTagResult {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are an editor and taxonomist for a developer news digest. Your readers are tech-savvy but busy. You assign topic tags from a fixed controlled vocabulary and never invent tags.

    {{ _.role("user") }}
    Classify and tag this article.

    Title: {{ title }}

    Content:
    {{ content }}

    1. Assign 1-2 categories.
    2. Assign a kind.
    3. Assign 1-3 tags from the vocabulary below, most relevant first. Pick the smallest set that captures what the article is actually about - do not pad to three. Use slugs from the vocabulary ONLY, copied exactly as written.

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

    Tag vocabulary — use these slugs ONLY, copied exactly as written:
    {% for t in vocabulary %}
    - {{ t.slug }}{% if t.description %}: {{ t.description }}{% endif %}
    {% endfor %}

    {{ ctx.output_format }}
  "#
}

function ClassifyKind(title: string, url: string) -> ClassifyKindResult {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a technical librarian who classifies AI developer content by format.

    {{ _.role("user") }}
    Classify this article's kind.

    Title: {{ title }}
    URL: {{ url }}

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

test categorize_and_tag_basic {
  functions [CategorizeAndTag]
  args {
    title "Anthropic releases Claude 4"
    content "Anthropic today launched Claude 4, a new flagship model. It features improved reasoning, a 1M-token context window, and native tool use. The model is available via API and Claude.ai starting today."
    vocabulary [
      {
        slug "models"
        description "new model releases, benchmarks, evals"
      }
      {
        slug "agents"
        description "autonomous agents: reasoning loops, planning"
      }
    ]
  }
}
