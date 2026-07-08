// Tag assignment — the main new LLM step under the redesigned schema.
// After summarize/categorize, assign 1-3 tags per article from the FIXED
// vocabulary below. The enum constrains the model to these exact slugs; the
// Python caller (pipeline/tags.py) still post-validates and drops anything
// off-list. Do NOT invent new tags — the 29 members here are the whole set.
//
// Member names use underscores (BAML identifiers can't contain hyphens); the
// @alias on each is the canonical slug written to the Tag table.

enum TagSlug {
  agents @alias("agents") @description("autonomous agents: reasoning loops, planning, long-running task execution")
  orchestration @alias("orchestration") @description("coordinating agents/workflows: multi-agent, agent frameworks/SDKs, deployment")
  tool_calling @alias("tool-calling") @description("agents/LLMs invoking external tools, APIs, functions (incl. MCP)")
  agent_memory @alias("agent-memory") @description("persistent/dynamic agent memory: vector stores, knowledge bases, long-term recall")
  context_optimization @alias("context-optimization") @description("managing the context window: compaction, retrieval into context, long-context")
  auditing @alias("auditing") @description("monitoring, logging, debugging, validating agent behavior")
  coding_assistants @alias("coding-assistants") @description("AI for software dev: code gen, completion, debugging, review")
  multimodal @alias("multimodal") @description("models/systems across text, image, audio, video and their applications")
  model_releases @alias("model-releases") @description("new/updated models: LLMs, VLMs, speech/vision - announcements, model cards")
  open_weights @alias("open-weights") @description("openly released model weights and open-source models/platforms")
  fine_tuning @alias("fine-tuning") @description("adapting pretrained models: LoRA, instruction tuning, RLHF")
  rag @alias("rag") @description("retrieval-augmented generation and semantic/vector search")
  evaluation @alias("evaluation") @description("benchmarks, metrics, methodologies for assessing models/agents")
  prompt_engineering @alias("prompt-engineering") @description("prompting techniques: system prompts, few-shot, structured, optimization")
  robotics @alias("robotics") @description("AI for physical/embodied systems: perception, control, embodied agents")
  sandboxing @alias("sandboxing") @description("isolated execution for agents/code: microVMs, secure runtimes, containment")
  product_launches @alias("product-launches") @description("new AI-powered products, platforms, commercial services")
  enterprise_ai @alias("enterprise-ai") @description("AI for business: workflow automation, internal tooling, enterprise deployments")
  local_ai @alias("local-ai") @description("on-device/offline AI: edge inference, local models, private local agents")
  distributed_training @alias("distributed-training") @description("scaling training across nodes/hardware: sharding, parallelism")
  safety @alias("safety") @description("model/agent safety and alignment: guardrails, fail-safes")
  security @alias("security") @description("securing agents/systems: prompt injection, adversarial attacks, misuse")
  privacy @alias("privacy") @description("protecting data/model secrecy: differential privacy, PII, confidential inference")
  inference_optimization @alias("inference-optimization") @description("faster/cheaper inference: latency, throughput, memory, serving")
  speculative_decoding @alias("speculative-decoding") @description("accelerating generation by predicting tokens ahead (draft models)")
  quantization @alias("quantization") @description("reducing precision/size for cheaper compute (INT8/4, GGUF, ...)")
  model_distillation @alias("model-distillation") @description("smaller/specialized models from larger teachers")
  cost_optimization @alias("cost-optimization") @description("cutting operational cost: token/compute reduction, cheaper routing/caching")
  hardware @alias("hardware") @description("AI hardware and accelerators: GPUs, TPUs, NPUs, edge chips")
}

// One article to tag. articleId round-trips so a batched response can be keyed
// back to the row (mirrors the id-keyed backfill batches).
class TagInput {
  articleId int
  title string
  summary string? @description("Short factual summary, if available")
}

class TagAssignment {
  articleId int
  tags TagSlug[] @description("1-3 tags from the fixed vocabulary; most relevant first")
}

function AssignTags(articles: TagInput[]) -> TagAssignment[] {
  client NvidiaGptOss
  prompt #"
    {{ _.role("system") }}
    You are a taxonomist for an AI developer news platform. You assign topic tags from a fixed controlled vocabulary. You never invent tags.

    {{ _.role("user") }}
    Assign 1-3 tags to each article, most relevant first. Only use tags from the vocabulary. Pick the smallest set that captures what the article is actually about - do not pad to three. Return one TagAssignment per input article, echoing its articleId.

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
  }
}
