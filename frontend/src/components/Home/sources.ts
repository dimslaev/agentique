// Hardcoded homepage "top selection" — one box per source. Kept in sync by a
// separate agent later; for now these are real articles pulled from prod
// plus current items sourced from each publisher's own site.
// No app article IDs exposed: every link points straight to the origin.

export type SourceArticle = {
  title: string
  url: string
  date: string // ISO date
  kind: string
  category: string
  tags: string[]
  /** Only set inside the aggregated newsletters box, where each row has its own origin. */
  from?: string
  /** Domain used to fetch a favicon for the `from` origin (newsletter rows only). */
  fromDomain?: string
}

export type Source = {
  slug: string
  name: string
  /** Utility label shown under the name, e.g. "Model lab", "Newsletters". */
  label: string
  /** Domain used to fetch the source's favicon as an avatar. */
  domain: string
  articles: SourceArticle[]
}

export const SOURCES: Source[] = [
  {
    slug: "anthropic",
    name: "Anthropic",
    label: "Model lab",
    domain: "anthropic.com",
    articles: [
      {
        title: "Introducing Claude Sonnet 5",
        url: "https://www.anthropic.com/news/claude-sonnet-5",
        date: "2026-06-30",
        kind: "model",
        category: "models",
        tags: ["Model Releases", "Anthropic"],
      },
      {
        title: "Claude Fable 5 and Claude Mythos 5",
        url: "https://www.anthropic.com/news/claude-fable-5-mythos-5",
        date: "2026-06-09",
        kind: "model",
        category: "models",
        tags: ["Model Releases", "Anthropic"],
      },
      {
        title: "KPMG integrates Claude across its core business and workforce",
        url: "https://www.anthropic.com/news/anthropic-kpmg",
        date: "2026-05-19",
        kind: "product",
        category: "dev",
        tags: ["Enterprise AI"],
      },
      {
        title: "Higher usage limits for Claude and a compute deal with SpaceX",
        url: "https://www.anthropic.com/news/higher-limits-spacex",
        date: "2026-05-06",
        kind: "announcement",
        category: "dev",
        tags: ["Anthropic"],
      },
    ],
  },
  {
    slug: "openai",
    name: "OpenAI",
    label: "Model lab",
    domain: "openai.com",
    articles: [
      {
        title: "Previewing GPT-5.6 Sol: a next-generation model",
        url: "https://openai.com/index/previewing-gpt-5-6-sol/",
        date: "2026-06-26",
        kind: "announcement",
        category: "models",
        tags: ["Model Releases", "OpenAI"],
      },
      {
        title:
          "From model to agent: Equipping the Responses API with a computer environment",
        url: "https://openai.com/index/equip-responses-api-computer-environment",
        date: "2026-03-11",
        kind: "blog",
        category: "dev",
        tags: ["Agents", "Tool Calling"],
      },
      {
        title: "Codex Security: now in research preview",
        url: "https://openai.com/index/codex-security-now-in-research-preview",
        date: "2026-03-06",
        kind: "product",
        category: "dev",
        tags: ["Coding Assistants", "Security"],
      },
      {
        title: "GPT-5.4: Efficient Frontier Model with 1M-Token Context",
        url: "https://openai.com/index/introducing-gpt-5-4",
        date: "2026-03-05",
        kind: "announcement",
        category: "models",
        tags: ["Model Releases", "Context Optimization"],
      },
    ],
  },
  {
    slug: "moonshot-ai",
    name: "Moonshot AI",
    label: "Model lab",
    domain: "kimi.com",
    articles: [
      {
        title: "PerceptionBench: Evaluating Atomic Visual Perception in MLLMs",
        url: "https://www.kimi.com/blog/perception-bench",
        date: "2026-07-16",
        kind: "paper",
        category: "research",
        tags: ["Multimodal", "Evaluation"],
      },
      {
        title: "Kimi K3: Open Frontier Intelligence",
        url: "https://www.kimi.com/blog/kimi-k3",
        date: "2026-07-14",
        kind: "model",
        category: "models",
        tags: ["Open Weights", "Model Releases"],
      },
      {
        title: "Kimi K2.7 Code: Open-Source Agentic Coding Model",
        url: "https://www.kimi.com/resources/kimi-k2-7-code",
        date: "2026-06-25",
        kind: "model",
        category: "models",
        tags: ["Coding Assistants", "Open Weights"],
      },
      {
        title: "Kimi Work: Next-Gen Desktop AI Agent for Knowledge Workers",
        url: "https://www.kimi.com/products/kimi-work",
        date: "2026-06-19",
        kind: "product",
        category: "dev",
        tags: ["Agents", "Enterprise AI"],
      },
    ],
  },
  {
    slug: "qwen",
    name: "Qwen",
    label: "Model lab",
    domain: "qwen.ai",
    articles: [
      {
        title: "Qwen3.7-Plus: Multimodal Agent Intelligence",
        url: "https://qwen.ai/blog?id=qwen3.7-plus",
        date: "2026-06-01",
        kind: "model",
        category: "models",
        tags: ["Agents", "Multimodal"],
      },
      {
        title: "Qwen3.7-Max: built for the agent era",
        url: "https://qwen.ai/blog?id=qwen3.7-max-preview",
        date: "2026-05-20",
        kind: "model",
        category: "models",
        tags: ["Agents", "Model Releases"],
      },
      {
        title: "Qwen3.7: The Agent Frontier",
        url: "https://qwen.ai/blog?id=qwen3.7",
        date: "2026-05-15",
        kind: "announcement",
        category: "models",
        tags: ["Agents", "Qwen"],
      },
      {
        title: "Qwen3.6 27b",
        url: "https://qwen.ai/blog?id=qwen3.6-27b",
        date: "2026-04-22",
        kind: "model",
        category: "models",
        tags: ["Open Weights", "Model Releases"],
      },
    ],
  },
  {
    slug: "mistral",
    name: "Mistral AI",
    label: "Model lab",
    domain: "mistral.ai",
    articles: [
      {
        title: "Your Prompts and Skills need a system of record",
        url: "https://mistral.ai/news/manage-prompts-and-skills-in-studio/",
        date: "2026-07-09",
        kind: "product",
        category: "dev",
        tags: ["Prompt Engineering"],
      },
      {
        title: "Introducing Robostral Navigate",
        url: "https://mistral.ai/news/robostral-navigate/",
        date: "2026-07-08",
        kind: "model",
        category: "models",
        tags: ["Robotics", "Model Releases"],
      },
      {
        title: "Leanstral 1.5: Proof Abundance for All",
        url: "https://mistral.ai/news/leanstral-1-5/",
        date: "2026-07-02",
        kind: "model",
        category: "models",
        tags: ["Model Releases"],
      },
      {
        title: "Introducing Mistral OCR 4",
        url: "https://mistral.ai/news/ocr-4/",
        date: "2026-06-23",
        kind: "model",
        category: "models",
        tags: ["Multimodal", "Model Releases"],
      },
    ],
  },
  {
    slug: "newsletters",
    name: "Newsletters",
    label: "Curated digests",
    domain: "resend.com",
    articles: [
      {
        from: "Ben's Bites",
        fromDomain: "bensbites.com",
        title:
          "Google open-weights DiffusionGemma delivers 3-5× speedup at comparable performance",
        url: "https://arstechnica.com/google/2026/06/googles-latest-diffusiongemma-open-ai-model-comes-with-a-4x-speed-boost",
        date: "2026-06-11",
        kind: "announcement",
        category: "models",
        tags: ["Open Weights", "Inference"],
      },
      {
        from: "The Rundown AI",
        fromDomain: "therundown.ai",
        title:
          "OpenAI launches GPT-5.4-Cyber permissive model for defensive security",
        url: "https://openai.com/index/scaling-trusted-access-for-cyber-defense/",
        date: "2026-04-15",
        kind: "announcement",
        category: "models",
        tags: ["Security", "OpenAI"],
      },
      {
        from: "TLDR",
        fromDomain: "tldr.tech",
        title:
          "Composer 2 offers frontier coding ability at $0.50 per M input tokens",
        url: "https://cursor.com/blog/composer-2",
        date: "2026-03-20",
        kind: "announcement",
        category: "dev",
        tags: ["Coding Assistants", "Inference"],
      },
      {
        from: "The Batch",
        fromDomain: "deeplearning.ai",
        title:
          "Claude Opus 4.5: Token-Efficient Model Improving on Previous Release",
        url: "https://www.anthropic.com/news/claude-opus-4-5",
        date: "2025-12-11",
        kind: "announcement",
        category: "models",
        tags: ["Anthropic", "Model Releases"],
      },
    ],
  },
]
