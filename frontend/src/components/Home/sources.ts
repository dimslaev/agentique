// Hardcoded homepage "top selection" — one box per source. Refreshed weekly by
// the `.agents/homepage-refresh.md` agent, which web-searches each publisher for
// their latest items and opens a PR editing this file.
// No app article IDs exposed: every link points straight to the origin (for
// aggregated newsletter rows, to the story's own source — official or not, as
// long as the item is confirmable).

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
        title: "A new way to reflect on how you use Claude",
        url: "https://www.anthropic.com/news/reflect-with-claude",
        date: "2026-07-09",
        kind: "product",
        category: "dev",
        tags: ["Anthropic"],
      },
      {
        title: "UST is bringing Claude to physical AI",
        url: "https://www.anthropic.com/news/ust-claude",
        date: "2026-07-08",
        kind: "product",
        category: "dev",
        tags: ["Enterprise AI", "Robotics"],
      },
      {
        title: "Introducing Claude Sonnet 5",
        url: "https://www.anthropic.com/news/claude-sonnet-5",
        date: "2026-06-30",
        kind: "model",
        category: "models",
        tags: ["Model Releases", "Anthropic"],
      },
      {
        title: "Claude Science, an AI workbench for scientists",
        url: "https://www.anthropic.com/news/claude-science-ai-workbench",
        date: "2026-06-30",
        kind: "product",
        category: "dev",
        tags: ["Enterprise AI"],
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
        title: "GPT-5.6: Frontier intelligence that scales with your ambition",
        url: "https://openai.com/index/gpt-5-6/",
        date: "2026-07-09",
        kind: "model",
        category: "models",
        tags: ["Model Releases", "OpenAI"],
      },
      {
        title: "GPT-5.6 is now the preferred model in Microsoft 365 Copilot",
        url: "https://openai.com/index/gpt-5-6-preferred-model-microsoft-365-copilot/",
        date: "2026-07-09",
        kind: "announcement",
        category: "dev",
        tags: ["OpenAI", "Enterprise AI"],
      },
      {
        title: "Introducing GPT-Live",
        url: "https://openai.com/index/introducing-gpt-live/",
        date: "2026-07-08",
        kind: "product",
        category: "dev",
        tags: ["OpenAI", "Multimodal"],
      },
      {
        title: "Previewing GPT-5.6 Sol: a next-generation model",
        url: "https://openai.com/index/previewing-gpt-5-6-sol/",
        date: "2026-06-26",
        kind: "announcement",
        category: "models",
        tags: ["Model Releases", "OpenAI"],
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
        date: "2026-07-16",
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
        title: "Qwen3.8-Max-Preview: 2.4T-parameter open-weight flagship",
        url: "https://officechai.com/ai/alibaba-qwen-3-8/",
        date: "2026-07-19",
        kind: "announcement",
        category: "models",
        tags: ["Model Releases", "Qwen"],
      },
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
          "Moonshot's Kimi K3 rivals OpenAI and Anthropic with 2.8T open weights",
        url: "https://www.cnbc.com/2026/07/17/moonshot-ai-kimi-k3-model-openai-anthropic-china.html",
        date: "2026-07-17",
        kind: "announcement",
        category: "models",
        tags: ["Open Weights", "Model Releases"],
      },
      {
        from: "The Rundown AI",
        fromDomain: "therundown.ai",
        title:
          "Alibaba previews 2.4T open-weight Qwen3.8-Max, second only to Fable 5",
        url: "https://finance.yahoo.com/technology/ai/articles/alibaba-qwen-unveils-preview-flagship-110209258.html",
        date: "2026-07-19",
        kind: "announcement",
        category: "models",
        tags: ["Open Weights", "Qwen"],
      },
      {
        from: "TLDR",
        fromDomain: "tldr.tech",
        title:
          "OpenAI ships GPT-5.6 to general availability with Sol, Terra and Luna",
        url: "https://openai.com/index/gpt-5-6/",
        date: "2026-07-09",
        kind: "announcement",
        category: "models",
        tags: ["Model Releases", "OpenAI"],
      },
      {
        from: "The Batch",
        fromDomain: "deeplearning.ai",
        title: "OpenAI's GPT-Live brings full-duplex voice to ChatGPT",
        url: "https://openai.com/index/introducing-gpt-live/",
        date: "2026-07-08",
        kind: "product",
        category: "dev",
        tags: ["OpenAI", "Multimodal"],
      },
    ],
  },
]
