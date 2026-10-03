// Feed topics: the "Topics" filter row. A topic is a set of tags and kinds the
// single-value filters cannot express; the API ORs within each list and ANDs
// the two.

export type TopicDef = {
  slug: string
  label: string
  /** Tag slugs, OR'd. */
  tags?: string[]
  /** Article kinds, OR'd. */
  kinds?: string[]
}

// Order is curated by hand: labs first, then model families, then the
// smaller-scope topics, then harnesses last.
export const TOPICS: TopicDef[] = [
  { slug: "anthropic", label: "Anthropic", tags: ["anthropic"] },
  { slug: "openai", label: "OpenAI", tags: ["openai"] },
  { slug: "google", label: "Google", tags: ["google"] },
  {
    slug: "open-weights",
    label: "Open weights",
    tags: ["kimi", "deepseek", "qwen", "glm", "mistral", "llama"],
  },
  {
    slug: "small-models",
    label: "Small models",
    tags: ["model-distillation", "quantization", "local-ai"],
  },
  {
    slug: "generative-media",
    label: "Beyond text",
    tags: ["multimodal", "media-generation", "voice-speech"],
  },
  {
    slug: "harness",
    label: "Harnesses",
    tags: ["orchestration", "tool-calling", "coding-assistants"],
  },
  {
    slug: "make-it-fast",
    label: "Make it fast",
    tags: [
      "inference-optimization",
      "hardware",
      "quantization",
      "cost-optimization",
    ],
  },
]

export function findTopic(slug: string): TopicDef | undefined {
  return TOPICS.find((t) => t.slug === slug)
}
