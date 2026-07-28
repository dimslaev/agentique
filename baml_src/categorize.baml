class CategoryOption {
  slug string
  name string
  description string @description("What belongs in this category, and the rule of thumb for it")
}

class CategoryMatch {
  url string
  categories string[] @description("0-3 slugs copied verbatim from the vocabulary; most relevant first. Empty means the article belongs in none of them.")
  kind ArticleKind @description("The article's format. Independent of its categories.")
}

// The whole editorial filter, in one call. An article matching no category is
// not stored at all, so an empty `categories` list is a normal, expected answer
// — not a failure. Batched: the vocabulary is sent once for several articles.
function MatchCategories(articles: ArticleInput[], categories: CategoryOption[]) -> CategoryMatch[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are the editor of an AI developer news site. You decide what gets published. The site covers a deliberately narrow beat, and most of what crosses your desk does not belong on it. Rejecting an article is the normal outcome, not a failure.

    {{ _.role("user") }}
    For each article below, decide which of these categories it belongs to.

    Categories — use these slugs ONLY, copied exactly as written:
    {% for c in categories %}
    - {{ c.slug }} ({{ c.name }}): {{ c.description }}
    {% endfor %}

    Rules:
    1. Assign at most 3 categories, most relevant first.
    2. Assign a category only if it is one of the article's PRIMARY subjects. A keyword mentioned in passing is not a subject. If an article merely name-drops a tool, that is not enough.
    3. If no category clearly applies, return an EMPTY list. This is common and correct. Do not stretch to find a match, and do not fall back to the broadest-sounding category.
    4. Do not pad. Most articles that match at all match one or two categories, not three.
    5. Judge the article, not the publisher. A post from an AI lab is not automatically about that lab.

    Worked examples:
    - "OpenAI releases GPT-OSS 20B" -> ai-labs, model-releases, open-weights
    - "Gemma 3 4B optimized for laptops" -> model-releases, open-weights, local-ai
    - "New GGUF release for GPT-OSS" -> open-weights, local-ai
    - "Run Mistral 14B on Ollama" -> local-ai
    - "llama.cpp adds FP8 support" -> local-ai, inference-optimization
    - "vLLM introduces speculative decoding" -> inference-optimization
    - "AWQ cuts VRAM usage by 40%" -> inference-optimization
    - "Cursor launches background agents" -> coding-agents
    - "Claude Code adds MCP support" -> coding-agents, tool-use-mcp
    - "Anthropic releases new MCP connector" -> ai-labs, tool-use-mcp
    - "OpenAI raises API prices" -> ai-labs
    - "Anthropic raises $5B" -> ai-labs
    - "EU passes new AI regulation" -> (empty)
    - "How we rewrote our CRDT merge algorithm" -> (empty)
    - "A survey of prompt engineering techniques" -> (empty)

    Separately, and independently of the categories, label each article's FORMAT:
    - Repo: GitHub or GitLab repository
    - Paper: academic paper, preprint, or long-form technical report
    - Model: model card or model release page (e.g. HuggingFace)
    - Blog: developer blog post, tutorial, how-to, or opinion piece
    - Product: product launch page or product website
    - Announcement: official release post from a major AI lab

    Format is not a category and does not influence one. An article you assign
    no categories to still gets a format.

    Return one CategoryMatch per input article, echoing its url exactly.

    Articles:
    {% for a in articles %}
    --- {{ a.url }} ---
    title: {{ a.title }}
    source: {{ a.source }}
    {% if a.snippet %}snippet: {{ a.snippet }}{% endif %}
    {% endfor %}

    {{ ctx.output_format }}
  "#
}

test match_open_weight_release {
  functions [MatchCategories]
  args {
    articles [
      {
        url "https://example.com/gpt-oss-20b"
        title "OpenAI releases GPT-OSS 20B under Apache 2.0"
        source "OpenAI"
        snippet "The weights are available on Hugging Face today, alongside GGUF conversions for local use."
      }
    ]
    categories [
      {
        slug "ai-labs"
        name "AI Labs"
        description "News about AI companies as organizations, independent of any specific model release."
      }
      {
        slug "model-releases"
        name "Model Releases"
        description "A new or updated AI model becomes available. About the release event itself."
      }
      {
        slug "open-weights"
        name "Open Weights"
        description "Models whose weights are publicly downloadable, not just callable via API."
      }
      {
        slug "inference-optimization"
        name "Inference & Optimization"
        description "Techniques and infrastructure making models faster, cheaper, or more efficient."
      }
    ]
  }
  @@assert(found_release, {{ "model-releases" in this[0].categories }})
  @@assert(found_weights, {{ "open-weights" in this[0].categories }})
  @@assert(capped, {{ this[0].categories|length <= 3 }})
  @@assert(has_kind, {{ this[0].kind|length > 0 }})
}

// The rejection path is the one that matters most: a filter that never says no
// is not a filter. Off-beat software engineering must come back empty.
test match_rejects_off_beat {
  functions [MatchCategories]
  args {
    articles [
      {
        url "https://example.com/crdt"
        title "How we rewrote our CRDT merge algorithm for 10x fewer conflicts"
        source "Some Eng Blog"
        snippet "A deep dive into conflict-free replicated data types and our new merge strategy."
      }
    ]
    categories [
      {
        slug "ai-labs"
        name "AI Labs"
        description "News about AI companies as organizations, independent of any specific model release."
      }
      {
        slug "coding-agents"
        name "Coding Agents"
        description "AI systems that help developers write, understand, review, and maintain software."
      }
      {
        slug "inference-optimization"
        name "Inference & Optimization"
        description "Techniques and infrastructure making models faster, cheaper, or more efficient."
      }
    ]
  }
  @@assert(rejected, {{ this[0].categories|length == 0 }})
  // Format is independent of category: a rejected article still has one, and
  // the pipeline never sees it, but a model that returns nothing here is
  // conflating the two judgements.
  @@assert(kind_still_set, {{ this[0].kind|length > 0 }})
}

// A passing mention of a coding agent must not pull the article into that lane.
test match_ignores_passing_mention {
  functions [MatchCategories]
  args {
    articles [
      {
        url "https://example.com/hiring"
        title "How we restructured our engineering org for 2026"
        source "Some Startup"
        snippet "We moved to squads, cut meetings, and yes, everyone uses Cursor now. Here is what changed about planning."
      }
    ]
    categories [
      {
        slug "coding-agents"
        name "Coding Agents"
        description "AI systems that help developers write, understand, review, and maintain software. Rule of thumb: if the primary user is a software developer writing code, it belongs here."
      }
      {
        slug "ai-labs"
        name "AI Labs"
        description "News about AI companies as organizations, independent of any specific model release."
      }
    ]
  }
  @@assert(rejected, {{ this[0].categories|length == 0 }})
}

test match_batch_echoes_urls {
  functions [MatchCategories]
  args {
    articles [
      {
        url "https://example.com/vllm"
        title "vLLM introduces speculative decoding"
        source "vLLM"
        snippet "Draft models now cut time-to-first-token by 40% on Llama workloads."
      }
      {
        url "https://example.com/anthropic-raise"
        title "Anthropic raises $5B at a $170B valuation"
        source "Reuters"
        snippet "The round was led by existing investors."
      }
    ]
    categories [
      {
        slug "ai-labs"
        name "AI Labs"
        description "News about AI companies as organizations: funding, acquisitions, pricing, partnerships, roadmaps."
      }
      {
        slug "inference-optimization"
        name "Inference & Optimization"
        description "Techniques and infrastructure making models faster, cheaper, or more efficient."
      }
      {
        slug "local-ai"
        name "Local AI"
        description "Models and tooling designed to run on local, edge, or on-device hardware."
      }
    ]
  }
  @@assert(both_returned, {{ this|length == 2 }})
  @@assert(urls_echoed, {{ this|map(attribute="url")|sort == ["https://example.com/anthropic-raise", "https://example.com/vllm"] }})
}
