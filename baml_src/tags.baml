class TagInput {
  articleId int
  title string
  summary string? @description("Short factual summary, if available")
}

class TagOption {
  slug string
  description string? @description("When to apply this tag")
}

class TagAssignment {
  articleId int
  tags string[] @description("1-3 slugs copied verbatim from the vocabulary; most relevant first")
}

function AssignTags(articles: TagInput[], vocabulary: TagOption[]) -> TagAssignment[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a taxonomist for an AI developer news platform. You assign topic tags from a fixed controlled vocabulary. You never invent tags.

    {{ _.role("user") }}
    Vocabulary — use these slugs ONLY, copied exactly as written:
    {% for t in vocabulary %}
    - {{ t.slug }}{% if t.description %}: {{ t.description }}{% endif %}
    {% endfor %}

    Assign 1-3 tags to each article, most relevant first. Only use slugs from the vocabulary above. Pick the smallest set that captures what the article is actually about - do not pad to three. Return one TagAssignment per input article, echoing its articleId.

    {% for a in articles %}
    --- Article {{ a.articleId }} ---
    title: {{ a.title }}
    {% if a.summary %}summary: {{ a.summary }}{% endif %}
    {% endfor %}

    {{ ctx.output_format }}
  "#
}

test assign_tags_basic {
  functions [AssignTags]
  args {
    articles [
      {
        articleId 1
        title "Running Llama 3 locally with 4-bit quantization on a laptop"
        summary "A guide to GGUF quantization for on-device inference."
      }
    ]
    vocabulary [
      {
        slug "quantization"
        description "reducing precision/size for cheaper compute (INT8/4, GGUF)"
      }
      {
        slug "local-ai"
        description "on-device/offline AI: edge inference, local models"
      }
      {
        slug "agents"
        description "autonomous agents: reasoning loops, planning"
      }
    ]
  }
}
