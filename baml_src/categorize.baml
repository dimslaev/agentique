class CategorizeResult {
  categories ArticleCategory[] @description("1-2 categories")
  kind ArticleKind
}

class ClassifyKindResult {
  kind ArticleKind
}

function Categorize(title: string, content: string) -> CategorizeResult {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a technical editor for a developer news digest. Your readers are tech-savvy but busy.

    {{ _.role("user") }}
    Classify this article.

    Title: {{ title }}

    Content:
    {{ content }}

    1. Assign 1-2 categories.
    2. Assign a kind.

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

test categorize_basic {
  functions [Categorize]
  args {
    title "Anthropic releases Claude 4"
    content "Anthropic today launched Claude 4, a new flagship model. It features improved reasoning, a 1M-token context window, and native tool use. The model is available via API and Claude.ai starting today."
  }
}
