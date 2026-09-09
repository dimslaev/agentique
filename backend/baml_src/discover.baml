// Batched relevance classifier for the Substack discovery crawler.
// One LLM call judges many candidate profiles at once (see ScoreArticles for
// the array-in/array-out batching pattern). Classification runs on cheap
// metadata (name + description) BEFORE any per-profile post fetch, and gates
// both DB insertion and whether the crawler recurses into that profile.

class ProfileInput {
  handle string @description("Substack owner handle, echoed back in the verdict")
  name string @description("Publication name")
  description string? @description("Publication hero text and/or author bio, if known")
}

class ProfileVerdict {
  handle string @description("Must exactly match the input handle")
  isAiRelated bool
  confidence int @description("0-100 confidence that AI/ML/LLMs is the PRIMARY focus")
}

function ClassifyProfiles(profiles: ProfileInput[]) -> ProfileVerdict[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You curate sources for a developer-focused AI news platform. For each Substack
    publication, decide whether artificial intelligence is its PRIMARY subject:
    AI/ML/LLMs, foundation models, AI engineering, AI products, or AI research.

    Mark isAiRelated = true ONLY when AI is clearly the main topic. Mark false for
    general tech, productivity, marketing, business, crypto, politics, lifestyle, or
    publications that merely mention AI in passing. When the signal is thin (sparse
    description, generic name), lean false and assign low confidence - the crawler
    prunes everything you reject, so false positives pollute the whole subtree.

    {{ _.role("user") }}
    Classify every profile. Echo each handle back EXACTLY as given.

    {% for p in profiles %}
    {{ loop.index }}. handle={{ p.handle }} | {{ p.name }}{% if p.description %} — {{ p.description }}{% endif %}
    {% endfor %}

    {{ ctx.output_format }}
  "#
}
