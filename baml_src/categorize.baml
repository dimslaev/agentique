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
    - "OpenAI releases GPT-OSS 20B" -> model-releases, open-weights
    - "Gemma 3 4B optimized for laptops" -> model-releases, open-weights, local-ai
    - "New GGUF release for GPT-OSS" -> open-weights, local-ai
    - "Run Mistral 14B on Ollama" -> local-ai
    - "llama.cpp adds FP8 support" -> local-ai, inference-optimization
    - "vLLM introduces speculative decoding" -> inference-optimization
    - "AWQ cuts VRAM usage by 40%" -> inference-optimization
    - "Cursor launches background agents" -> coding-agents
    - "Claude Code adds MCP support" -> coding-agents, tool-use-mcp
    - "Anthropic releases new MCP connector" -> tool-use-mcp
    - "New reranker cuts retrieval latency in half" -> rag, inference-optimization
    - "Chunking strategies for long PDFs" -> rag
    - "Agents that remember across sessions" -> rag
    - "FLUX 2 image model released with open weights" -> model-releases, open-weights, multimodal
    - "Real-time voice agent with 200ms latency" -> multimodal
    - "Vision model reads screenshots for browser agents" -> multimodal, tool-use-mcp
    - "Prompt injection escapes an agent sandbox" -> security-safety
    - "Running agent code in microVMs" -> security-safety
    - "Red-teaming results for a frontier model" -> security-safety

    Rejected — no category applies. Note that the first three are ABOUT AI
    companies. There is no category for corporate news, and that is deliberate:
    - "OpenAI raises API prices" -> (empty)
    - "Anthropic raises $5B" -> (empty)
    - "AI lab hires a new head of research" -> (empty)
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
  // Corporate funding news has no category since AI Labs was removed. A mixed
  // batch must reject one and keep the other, not smear a verdict across both.
  @@assert(vllm_matched, {{ this|selectattr("url", "eq", "https://example.com/vllm")|map(attribute="categories")|first|length > 0 }})
  @@assert(funding_rejected, {{ this|selectattr("url", "eq", "https://example.com/anthropic-raise")|map(attribute="categories")|first|length == 0 }})
}

// RAG vs Tool Use is the sharpest new boundary: both reach outside the model.
// Retrieving KNOWLEDGE to read is RAG; invoking an ACTION is tool use.
test match_retrieval_is_rag_not_tool_use {
  functions [MatchCategories]
  args {
    articles [
      {
        url "https://example.com/reranker"
        title "A reranker that doubles retrieval precision on long PDFs"
        source "Some Blog"
        snippet "We chunk documents, embed them, and rerank the top 100 hits before putting them in the context window."
      }
    ]
    categories [
      {
        slug "rag"
        name "RAG"
        description "Retrieval-augmented generation: pulling external knowledge into a model's context before it answers. Vector search, embeddings for retrieval, chunking, rerankers, agent memory. The distinction from Tool Use & MCP is what the model does with the external system: retrieving KNOWLEDGE to read is RAG, invoking an ACTION is tool use."
      }
      {
        slug "tool-use-mcp"
        name "Tool Use & MCP"
        description "Models interacting with external software and systems. The defining feature is that the model performs actions beyond generating text."
      }
    ]
  }
  @@assert(is_rag, {{ "rag" in this[0].categories }})
  @@assert(not_tool_use, {{ "tool-use-mcp" not in this[0].categories }})
}

test match_voice_and_vision_are_one_category {
  functions [MatchCategories]
  args {
    articles [
      {
        url "https://example.com/voice"
        title "Real-time voice agent answers in under 200ms"
        source "Some Lab"
        snippet "Streaming speech-to-text into the model and text-to-speech back out, with no perceptible turn delay."
      }
      {
        url "https://example.com/flux"
        title "FLUX 2 image model released with open weights"
        source "Black Forest Labs"
        snippet "The diffusion weights are on Hugging Face today."
      }
    ]
    categories [
      {
        slug "multimodal"
        name "Multimodal"
        description "AI that works in any modality other than text: image, video, audio, speech, or several at once. Includes image and video generation, vision-language models, OCR, text-to-speech, speech-to-text, voice agents, and cross-modal systems."
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
    ]
  }
  @@assert(voice_is_multimodal, {{ "multimodal" in this[0].categories }})
  @@assert(image_is_multimodal, {{ "multimodal" in this[1].categories }})
  @@assert(image_also_a_release, {{ "model-releases" in this[1].categories }})
}

// Sandboxing sits in Security & Safety, not Tool Use, even though the subject
// is an agent running code: the story is the containment.
test match_sandboxing_is_security {
  functions [MatchCategories]
  args {
    articles [
      {
        url "https://example.com/sandbox"
        title "Prompt injection escaped our agent sandbox"
        source "Some Security Blog"
        snippet "An injected instruction let agent-generated code read files outside the microVM boundary."
      }
    ]
    categories [
      {
        slug "security-safety"
        name "Security & Safety"
        description "Keeping models and agents from causing harm, and keeping attackers out of them. Prompt injection, jailbreaks, red-teaming, guardrails, sandboxing and isolated execution, misuse prevention, privacy. Sandboxing belongs here rather than in Tool Use & MCP: the story is the containment, not the capability."
      }
      {
        slug "tool-use-mcp"
        name "Tool Use & MCP"
        description "Models interacting with external software and systems. The defining feature is that the model performs actions beyond generating text."
      }
      {
        slug "coding-agents"
        name "Coding Agents"
        description "AI systems that help developers write, understand, review, and maintain software."
      }
    ]
  }
  @@assert(is_security, {{ "security-safety" in this[0].categories }})
}
