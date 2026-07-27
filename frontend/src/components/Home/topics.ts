// Landing-page topic boxes.
//
// A box earns its place only if the /feed sidebar cannot express it. /feed is
// single-select (one tag, one kind, one category), so a union of tags or a
// tag-crossed-with-kind is a box; a lone `tag=security` is just a filter chip
// and does not belong here.
//
// v1 is frontend-only: each box expands into one readArticles call per
// tag x kind pair and merges client-side. That is provably correct for unions
// and tag-and-kind boxes — if an article is in the merged top-10 by date, at
// most 9 are newer overall, so at most 9 are newer within any single
// constituent request, and it is therefore in that request's own top-10.
//
// It is NOT correct for tag-and-tag intersections: date sort gives the
// constituent requests no shared ordering, and `agent-security` recovers 1 of
// its true top-10 even when fetching the API maximum. Those boxes wait for the
// backend endpoint. See plans/topic-boxes-homepage.md.

export type TopicDef = {
  slug: string
  label: string
  blurb: string
  /** Tag slugs, OR'd: one request each, crossed with `kinds`. */
  tags?: string[]
  /** Article kinds, OR'd: one request each, crossed with `tags`. */
  kinds?: string[]
  category?: string
}

/** Rows shown per box, and the page size of every underlying request. */
export const BOX_LIMIT = 10

/** Newest first, matching /feed's own default. */
export const BOX_SORT = "published_at-desc"

// Order matters twice over. Boxes load as they scroll into view, so the first
// row decides both what a visitor sees first and what the page costs on first
// paint. Leading with the strongest boxes alone was measurably wrong: harness,
// make-it-fast and open-challengers expand to 6+4+6 requests, and putting them
// up top fired 22 of the page's 30 requests before the reader scrolled at all.
//
// So the first row is boxes that are strong *and* single-request; the wide
// multi-tag lanes sit below the fold where their cost is paid on scroll.
export const TOPICS: TopicDef[] = [
  {
    slug: "open-source-drops",
    label: "Open source drops",
    blurb: "New repos worth cloning",
    kinds: ["repo"],
    category: "dev",
  },
  {
    slug: "anthropic",
    label: "Anthropic",
    blurb: "Claude, Claude Code, and everything around them",
    tags: ["anthropic"],
  },
  {
    slug: "new-models",
    label: "New models",
    blurb: "Fresh model announcements",
    kinds: ["announcement"],
    category: "models",
  },
  {
    slug: "harness",
    label: "Agent harnesses",
    blurb: "The tooling wrapped around the model — runners, loops, CLIs",
    tags: ["orchestration", "agents", "coding-assistants"],
    kinds: ["repo", "product"],
  },
  {
    slug: "make-it-fast",
    label: "Make it fast",
    blurb: "Inference speed, GPUs, quantization, cost per token",
    tags: [
      "inference-optimization",
      "hardware",
      "quantization",
      "cost-optimization",
    ],
  },
  {
    slug: "generative-media",
    label: "Beyond text",
    blurb: "Vision, video, audio and voice models",
    tags: ["multimodal", "media-generation", "voice-speech"],
  },
  {
    slug: "small-models",
    label: "Small models",
    blurb: "Distilled, quantized, and small enough to run yourself",
    tags: ["model-distillation", "quantization", "local-ai"],
  },
  {
    slug: "launches",
    label: "Launches",
    blurb: "Products shipping for developers",
    kinds: ["product"],
    category: "dev",
  },
  {
    slug: "open-challengers",
    label: "Open challengers",
    blurb: "The open labs chasing the frontier",
    tags: ["kimi", "deepseek", "qwen", "glm", "mistral", "llama"],
  },
  {
    slug: "open-model-drops",
    label: "Open weights",
    blurb: "Open-weight releases, not commentary about them",
    tags: ["open-weights"],
    kinds: ["model", "announcement"],
  },
  {
    slug: "openai",
    label: "OpenAI",
    blurb: "Models, products and research from OpenAI",
    tags: ["openai"],
  },
  {
    slug: "papers",
    label: "Papers",
    blurb: "Research worth the read",
    kinds: ["paper"],
    category: "research",
  },
  {
    slug: "google",
    label: "Google",
    blurb: "Gemini, Gemma and DeepMind",
    tags: ["google"],
  },
]
