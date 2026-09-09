// Landing-page topic boxes.
//
// A box earns its place only if the /feed sidebar cannot express it. /feed is
// single-select (one tag, one kind, one category), so a union of tags or a
// tag-crossed-with-kind is a box; a lone `tag=security` is just a filter chip
// and does not belong here.
//
// v1 is frontend-only: each box expands into one readArticles call per
// tag x kind pair and merges client-side. That is provably correct for unions
// and tag-and-kind boxes — if an article is in the merged top-10 by score, at
// most 9 outrank it overall, so at most 9 outrank it within any single
// constituent request, and it is therefore in that request's own top-10. The
// argument holds for any single total order the requests share; it held for
// date before and holds for score now.
//
// It is NOT correct for tag-and-tag intersections: the constituent requests
// share no ordering there, and `agent-security` recovers 1 of its true top-10
// even when fetching the API maximum. Those boxes wait for the backend
// endpoint. See plans/topic-boxes-homepage.md.

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

/**
 * Best first. The landing page is a "what mattered" view, not a river —
 * /feed is where you go for newest-first.
 */
export const BOX_SORT = "score-desc"

/**
 * How far back a box looks. Score sort with no window would pin the same
 * high scorers to the page for months; 14 days keeps it moving without
 * emptying the thinner boxes the way 7 does.
 */
export const BOX_WINDOW_DAYS = 14

// Order is curated by hand, 3 per row (grid wraps at lg:grid-cols-3):
// labs first, then model-news, then the smaller-scope lanes, then
// launches/papers/leftovers last.
export const TOPICS: TopicDef[] = [
  {
    slug: "anthropic",
    label: "Anthropic",
    blurb: "Claude, Claude Code, and everything around them",
    tags: ["anthropic"],
  },
  {
    slug: "openai",
    label: "OpenAI",
    blurb: "Models, products and research from OpenAI",
    tags: ["openai"],
  },
  {
    slug: "google",
    label: "Google",
    blurb: "Gemini, Gemma and DeepMind",
    tags: ["google"],
  },
  {
    slug: "new-models",
    label: "New models",
    blurb: "Fresh model announcements",
    kinds: ["announcement"],
    category: "models",
  },
  {
    slug: "open-challengers",
    label: "Open challengers",
    blurb: "The open labs chasing the frontier",
    tags: ["kimi", "deepseek", "qwen", "glm", "mistral", "llama"],
  },
  {
    slug: "small-models",
    label: "Small models",
    blurb: "Distilled, quantized, and small enough to run yourself",
    tags: ["model-distillation", "quantization", "local-ai"],
  },
  {
    slug: "generative-media",
    label: "Beyond text",
    blurb: "Vision, video, audio and voice models",
    tags: ["multimodal", "media-generation", "voice-speech"],
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
    slug: "launches",
    label: "Launches",
    blurb: "Products shipping for developers",
    kinds: ["product"],
    category: "dev",
  },
  {
    slug: "open-source-drops",
    label: "Open source drops",
    blurb: "New repos worth cloning",
    kinds: ["repo"],
    category: "dev",
  },
  {
    slug: "harness",
    label: "Agent harnesses",
    blurb: "The tooling wrapped around the model — runners, loops, CLIs",
    tags: ["orchestration", "agents", "coding-assistants"],
    kinds: ["repo", "product"],
  },
  {
    slug: "papers",
    label: "Papers",
    blurb: "Research worth the read",
    kinds: ["paper"],
    category: "research",
  },
]
