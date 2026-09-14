class ScoredArticle {
  url string
  score int @description("1-100 developer-actionability rating")
  reason string @description("One short sentence naming what decided the score: out of scope, the evidence shown or missing, the reach, or the rule that capped it.")
}

// Nemotron directly, no Nvidia fallback: falling back to another model would
// mix two judges' scales in one feed (see the Nvidia wrapper in clients.baml). A NIM
// outage holds the batch for the next run, as summaries already do.
function ScoreArticles(articles: ArticleInput[]) -> ScoredArticle[] {
  client Nemotron
  prompt #"
    {{ _.role("system") }}
    You are a senior editorial analyst at a developer news platform. You rate articles on how much they help someone building with AI. You are precise and consistent, and when something is thin you say so with a low number.

    {{ _.role("user") }}
    Score every article 1-100.

    FIRST — IS IT IN SCOPE?
    In scope: AI, ML, LLMs, foundation models, and the tools and infrastructure developers use to build with them. That includes skills, plugins, hooks, MCP servers and subagents for coding agents such as Claude Code or Codex, and security news with AI at its center: stolen AI API keys, attacks through AI tools, agents or model hubs.
    Everything else scores 1-14 — stop there, do not read the rest of this guide: crypto/web3 (even when the post says "agents"), general programming (editors, parsers, version control, data structures, memory management), non-AI open source, security and formal verification with no AI component, classic ML/statistics tutorials (tree models, regression, tabular features), chip packaging and supply chain, regulation, politics, lawsuits, corporate drama, funding and hiring.

    THEN — HOW MUCH DOES IT GIVE A BUILDER?
    Two things decide the number:
      EVIDENCE — what is actually shown? Runnable code, downloadable weights, a measured result with its method stated, or concrete steps a reader can copy. A number in a headline with no method behind it is a claim, not evidence — discount it hard, and the bigger the claim the harder.
      REACH — how many people building with AI does it change something for? A frontier release or a runtime everyone uses is high. A weekend project, demo, or niche integration is low.

    BANDS
    Absolute, not relative to this batch. Every example below is a real item, correctly scored.

    90-100 — Strong evidence, high reach. Frontier or open-weight releases you can run today, landmark results. Rare: a handful a month. 97+ is genuinely field-moving.
      97  "Kimi K3: Open Frontier Intelligence" [Moonshot AI] — open 3T-class weights, frontier claims, downloadable.

    80-89 — Real technical substance from a credible source, usable today. Also where a practitioner writeup lands when the technique is spelled out and reusable, first-party or not.
      88  "vLLM integrates Hugging Face Transformers for production-grade inference" [HF Blog] — official integration, removes porting work for every model author.
      85  "TurboPrefill: 2.7x faster than llama.cpp Pipeline Parallel on Llama-3-70B" [HN, 240 points] — upstream PR, stated hardware, measured speedup.
      85  "Optimizing Claude 3 Code's System Prompt for Efficiency and Output Quality" [AI Hero] — third party, but the method is concrete and a reader can apply it.
      85  "Qwen3.6-35B-A3B" [AI News] huggingface.co/Qwen/Qwen3.6-35B-A3B — found through an aggregator, but the URL is Qwen's own model card: a first-party open-weight release, not a rewrite.
      82  "Qwen3.6-27B KV Cache Quantization in vLLM: Accuracy, Memory, and Speed" [Kaitchup] — measured comparison a reader can rerun.
      80  "Ollama ships native support for a major open model family" [HN] — a runtime a huge share of builders already run, and the capability lands for all of them at once; adoption, not new research, so bottom of the band.

    70-79 — Useful but narrow, or well-made with modest novelty. Community writeups, series posts, and think pieces that leave a builder with something belong here.
      75  "My self-sovereign local LLM setup, April 2026" [personal blog] — no scripts, but named tooling and measured tok/sec across real hardware; a reader can rebuild from it.
      74  "Running Gemma 4 26B at 5 tokens/sec on a 13-year-old Xeon with no GPU" [HN] — reproducible with exact flags, but narrow.
      74  "Orchestrating AI code review at scale" [Hacker News] blog.cloudflare.com — seven review agents per merge request, architecture and trade-offs spelled out; no A/B numbers, but a team can copy the design.
      72  "Running a one-trillion-parameter LLM locally on an AMD Ryzen AI Max+ cluster" [Hacker News] amd.com — exact hardware and llama.cpp RPC steps; reproducible without a benchmark table.
      72  "We measured agent token cost across 40 repos before picking a context strategy" [Eng blog] — written for founders and leads, not the coder, but real data with a stated method and a decision it drove.
      70  "What 18 agent-built PRs cost us in context tokens" [Vendor blog] — measured from their own sessions with the method stated and it names a real cost line item; it also pitches their product, which neither adds nor subtracts.
      70  "Set Up a $0 Cloud VM to Run Your Hermes Agent (Part 1)" [AI Weekender] — serial newsletter post, but the steps work.
      70  "Why Human Language is the New Code (and How to Write It)" [Substack] — think piece, worth a builder's time.
      70  "Orchestrating agents just got 10x easier, check out Temporal" [x.com] — social post, but a real tool behind it.

    55-69 — Minor tools, incremental product news, competent commentary, demos.
      65  "A month of local-LLM releases, rounded up" [Substack] — competent digest, saves some tab-hopping, but no analysis of its own.
      62  "llama.cpp adds a --cache-reuse flag for partial prompt matches" [HN] — real and merged upstream, but a single knob most builders never touch.
      60  "How Heurist Finance built an AI-native investment workbench on Amazon Bedrock AgentCore" [AWS Machine Learning] — a customer story selling the platform; architecture boxes, no measured result.
      60  "A Mathematical Framework for Transformer Circuits" [HN, transformer-circuits.pub/2021/...] — foundational, but a 2021 paper resurfacing years later is not news.
      55  "I built a TUI for chatting with Ollama" [HN] — it works, but it is small and a dozen others do the same thing.
      55  "GLM-5.3 is 50% off through DigitalOcean on AI Gateway" [Vercel] — a price notice; the model release it points at was the news.

    35-54 — Unverified solo projects, marketing and landing pages, big numbers with no method.
      45  "LLMrPro: free LLM balancer combines local machines with cloud fallback" [HN, 4 points, 0 comments] — unknown solo repo in a crowded category, and nobody read it.
      45  "Pinecone vs Amazon S3 Vectors" [Pinecone] — the vendor's own comparison page: a sales page, not an article.
      35  "SigMap cuts prompt count by 49% across 90 coding tasks" [HN, 3 points, 1 comment] — landing page, extraordinary numbers, no method or repo.

    15-34 — Slop, SEO bait, advocacy and campaign pages, manifestos, content-free.

    1-14 — Out of scope only. An in-scope article never goes below 15: this band means "wrong subject", not "bad".

    RULES
    - A first-party release post on a major lab's own domain (openai.com, anthropic.com, deepmind.google, mistral.ai, kimi.com, ai.meta.com, qwen.ai, huggingface.co/blog, an official model card) never scores below 70. Aggregators retitle these into something that reads like a rewrite — judge the release, not the headline someone put on it. The floor is for releases — a model, API, tool or capability shipping — not for everything on the domain: a customer story, case study, event recap or marketing page on a lab's site is judged like any vendor post.
    - The [source] tag says where we found the link — often an aggregator, a newsletter or Hacker News — not who wrote it. Decide first-party versus rewrite from the URL: the maker's own site, blog, docs, x.com account, huggingface.co/<maker> or github.com/<maker> is first-party, whatever the tag says. A company's own release of its own model or developer tool there is a release and is judged as one — never as a notice or a rewrite.
    - A new model that builders can download or call today, released by an established maker — a known lab, a major tech company, or the company behind a tool a large share of builders already use (Cursor, Black Forest Labs, Xiaomi, Microsoft, NVIDIA, DeepSeek) — is a release even when the maker is not on the list above. It lands 70 or above, with REACH deciding how far; its self-reported benchmarks neither add nor subtract. An unknown company announcing a model on a landing page with big claims and no weights, API docs or model card is still a landing page (35-54).
    - A piece written for founders or tech leads — someone deciding what their team builds with, not writing the code — is in scope, judged on the same EVIDENCE bar as everything else: data with a stated method, a named decision it informs, or steps someone can follow. One that clears it lands 55-79. A polished piece with only an argument behind it still caps at 40, as do pure careers, business strategy, funding, and hiring. "The model is the brain, everything else is the desk" is a metaphor, not evidence.
    - A vendor's own blog post is scored on its evidence like anything else. Real numbers with a stated method count even when the post also pitches the vendor's product; a product pitch with no method behind it does not (see the 35-54 band).
    - A customer case study on a cloud or platform vendor's blog ("How X built Y with Bedrock / AgentCore / Vertex / Azure") is marketing for the platform: it caps at 60 unless it reports a measured result with its method stated. A company writing up how it built something for its own engineering — its architecture, trade-offs and what went wrong — is a practitioner write-up, not a case study: judge it on how much a team could copy, not on how many people use that company's product.
    - An availability or pricing notice — an existing model or tool now available on another platform, a price cut, a discount, a new region or quota — caps at 55. The release it points at is the news; this is a changelog line. A new model or product launching is a release, not a notice, however short the post that announces it.
    - A third-party rewrite of someone else's release or paper (news aggregators, SEO explainers, reseller and wrapper sites) scores about 10 below what the release itself would earn, and never above 80: the evidence lives in the primary source, not the retelling. One that only restates the announcement, adding nothing, scores about 20 below. Start from what the release itself would earn in the bands above (a frontier model launch is 90+), not from a floor, then subtract: a rewrite is often the only copy of a launch the feed gets, and a major launch retold still clears the bar. This is only for pieces whose subject is the announcement itself: a post that tests, benchmarks or builds with a released model is not a rewrite, and is judged on its own evidence.
    - A page that is not an article — a documentation index, a product or landing page, a model catalog, a pricing page, a vendor's own "X vs Y" comparison — belongs in 35-54, however strong the product behind it. So does a standing page for something that already exists — a product homepage, a model or tool page with no launch news on it — even on a lab's own domain: the release floor is for launches.
    - Old work resurfacing is not news. If the URL or the text dates the piece more than six months before the seen date (a /2021/ path, a 2024 arXiv id, "published March 2025"), it caps at 60, however good it is.
    - An independent or personal developer blog is scored on the same EVIDENCE and REACH as anything else — no penalty for having no institution behind it, no bonus for the author's name. A setup writeup, a debugging story, or a benchmark on the author's own hardware lands where its detail puts it: concrete and reproducible reaches 70-79, a spelled-out reusable technique 80-89, thin or purely reflective posts below.
    - Missing numbers are not missing evidence. Exact setup steps, or a system design spelled out in enough detail for a team to copy it, are evidence on their own: such a piece lands 70-79 even with no benchmark table. "No measured results" only drags down a piece with nothing else behind it — a claim, a pitch, a landing page. Working code alone does not lift a small tool: a weekend repo that runs is still a minor tool (55-69). Advice is not steps: tips, model-picking guides and what-I-learned lists with nothing a reader can run or check are commentary (55-69), and dramatic reports of agent behavior with nothing checkable behind them are claims.
    - A proposed spec, standard, or protocol with no users beyond its author caps at 70, even with a reference implementation. Anyone can publish a spec; adoption is what makes one matter.
    - Empty snippet means you are judging a title alone → cap 70.
    - Score against the whole field, not against the others in this batch. A weak batch produces low scores; that is the correct outcome.
    - Topic is never a bonus. Local inference, quantization, privacy, on-device, and token cost are common subjects, not merit. A shallow post about local inference scores below a rigorous post about anything else.
    - Trust tag: high +3, low -3, applied after the band is chosen. It breaks ties; it does not move an article between bands.
    - Traction, when given, is how the public actually received the item where it was posted, and it is evidence about REACH — the one thing a title cannot fake. A submission sitting at single-digit points and no comments is a post nobody read: it caps at 45 regardless of how the title is written, and "Show HN"-style self-promotion there caps at 35. Strong traction (hundreds of points, a live discussion) confirms reach; it does not add evidence, so it never lifts a thin item past 70 on its own. No traction field means the source has no such signal — judge on evidence alone, do not assume either way.
    - Use the whole range. 74, 68, and 52 are real scores. Most items are not 90s: if you are about to give a batch of five four scores above 85, you have stopped discriminating. Re-read the bands and place each one absolutely.

    Articles:
    {% for a in articles %}
    {{ loop.index }}. [{{ a.source }}] "{{ a.title }}" - {{ a.url }}{% if a.trust %} [trust: {{ a.trust }}]{% endif %}{% if a.traction %} [traction: {{ a.traction }}]{% endif %}{% if a.seen_on %} [seen: {{ a.seen_on }}]{% endif %}
    {% if a.snippet %}   {{ a.snippet }}{% else %}   (no content available){% endif %}
    {% endfor %}

    {{ ctx.output_format }}
  "#
}

test score_frontier_release {
  functions [ScoreArticles]
  args {
    articles [
      {
        url "https://www.kimi.com/blog/kimi-k3"
        title "Kimi K3: Open Frontier Intelligence"
        source "Moonshot AI"
        snippet "Kimi K3 is the world's first open 3T-class model - frontier performance across coding, knowledge work, and reasoning."
        trust "medium"
      }
    ]
  }
}

test score_out_of_scope {
  functions [ScoreArticles]
  args {
    articles [
      {
        url "https://x.com/NEARProtocol/status/2076729054632231274"
        title "NEAR Launches General Availability of Confidential Intents via 1Click Swap API for Developer Integration"
        source "Aligned News"
        snippet "NEAR released Confidential Intents for general use through its 1Click Swap API."
        trust "medium"
      }
    ]
  }
}

// Separates practitioner content from advocacy. The newsletter walkthrough has
// steps a reader can follow and should clear 65; the campaign page has nothing
// technical and stays below 35.
test score_practitioner_vs_advocacy {
  functions [ScoreArticles]
  args {
    articles [
      {
        url "https://aiweekender.substack.com/p/set-up-a-0-cloud-vm-to-run-your-hermes"
        title "Set Up a $0 Cloud VM to Run Your Hermes Agent (Part 1)"
        source "AI Weekender"
        snippet "This post is the first in a series. It details setting up a free, always-on Linux virtual machine. This VM will host a Hermes agent."
        trust "medium"
      }
      {
        url "https://righttointelligence.org/"
        title "Protect your right to run local AI"
        source "Hacker News"
        snippet "A campaign page advocating the right to run local AI. It calls for protecting the ability to run models on your own hardware."
        trust "medium"
        traction "18 points, 6 comments on Hacker News"
      }
    ]
  }
}

// Founder-audience is in scope. The piece with measured data and a decision
// behind it clears the threshold; the polished argument with nothing to act on
// stays at or under 40; a vendor post with real numbers and a stated method
// clears it too, its product pitch notwithstanding.
test score_founder_audience {
  functions [ScoreArticles]
  args {
    articles [
      {
        url "https://example.com/blog/agent-token-cost-study"
        title "We measured agent token cost across 40 repos before picking a context strategy"
        source "Engineering blog"
        snippet "Over six weeks we logged context-token usage for coding agents across 40 internal repos, with the measurement method and per-repo numbers. Here is how it shaped the retrieval approach we chose."
        trust "medium"
      }
      {
        url "https://example.com/blog/why-agents-change-the-org"
        title "Why AI agents change how you should structure your engineering org"
        source "Substack"
        snippet "A case that agents shift the unit of work from the team to the individual, and what that means for how founders should plan headcount."
        trust "medium"
      }
      {
        url "https://vendor.example.com/blog/stop-the-context-tax"
        title "What 18 agent-built PRs cost us in context tokens"
        source "Vendor blog"
        snippet "Each agent-built PR in our codebase averaged $65 in context-token overhead, peaking near 975k tokens. Our semantic navigation layer cuts that."
        trust "medium"
      }
    ]
  }
}

// Regression: a big percentage in a title with nothing behind it must not beat
// a measured result. Expect the landing page well below the benchmark post.
test score_unverified_claim_vs_measured {
  functions [ScoreArticles]
  args {
    articles [
      {
        url "https://sigmap.io/"
        title "SigMap cuts prompt count by 49% across 90 coding tasks"
        source "Hacker News"
        snippet "SigMap cuts prompt count by 49.2% on 90 coding tasks. It reduces token usage by 97% and runs offline with zero dependencies."
        trust "medium"
        traction "3 points, 1 comments on Hacker News"
      }
      {
        url "https://github.com/ggml-org/llama.cpp/pull/24219"
        title "TurboPrefill: 2.7x faster than llama.cpp Pipeline Parallel on Llama-3-70B"
        source "Hacker News"
        snippet "TurboPrefill implements intra-prompt pipeline scheduling for multi-GPU prefill. On Llama-3-70B it runs 2.7x faster than llama.cpp pipeline parallel."
        trust "medium"
        traction "240 points, 96 comments on Hacker News"
      }
    ]
  }
}

// The 2026-09-13 caps, all from a review of the ten runs before it. Expect the
// discount notice at or under 55, the AWS customer story at or under 60, the
// comparison page in 35-54, and the resurfaced 2021 paper at or under 60.
test score_notices_case_studies_and_old_work {
  functions [ScoreArticles]
  args {
    articles [
      {
        url "https://vercel.com/changelog/glm-5-3-is-50-off-through-digitalocean-on-ai-gateway"
        title "GLM-5.3 is 50% off through DigitalOcean on AI Gateway"
        source "Vercel"
        snippet "GLM-5.3 is now 50% off when routed through DigitalOcean on AI Gateway, through the end of the month."
        trust "medium"
        seen_on "2026-09-03"
      }
      {
        url "https://aws.amazon.com/blogs/machine-learning/how-heurist-finance-built-an-ai-native-investment-workbench-on-amazon-bedrock-agentcore/"
        title "How Heurist Finance built an AI-native investment workbench on Amazon Bedrock AgentCore"
        source "AWS Machine Learning"
        snippet "Heurist Finance uses Amazon Bedrock AgentCore to turn a chat into full-stack financial research. AgentCore payments buy the premium data each query needs."
        trust "medium"
        seen_on "2026-09-10"
      }
      {
        url "https://www.pinecone.io/compare/elasticsearch"
        title "Pinecone vs Elasticsearch"
        source "Pinecone"
        snippet "Pinecone separates storage and compute, so there is no cluster to manage. Elasticsearch stores vectors in the same shards as text."
        trust "medium"
        seen_on "2026-09-05"
      }
      {
        url "https://transformer-circuits.pub/2021/framework/index.html"
        title "A Mathematical Framework for Transformer Circuits"
        source "Hacker News"
        snippet "We propose a way to reverse engineer transformer computations, mapping layers to readable steps."
        trust "medium"
        traction "132 points, 21 comments on Hacker News"
        seen_on "2026-09-13"
      }
    ]
  }
}

// From the 2026-09-13 rescore, where Nemotron read the aggregator in [source]
// as the author and called first-party releases rewrites or notices, and
// dropped a copyable engineering write-up for having no benchmark table.
// Expect all three at 70 or above.
test score_source_tag_is_not_the_author {
  functions [ScoreArticles]
  args {
    articles [
      {
        url "https://huggingface.co/Qwen/Qwen3.6-35B-A3B"
        title "Qwen3.6-35B-A3B sparse MoE model beats Qwen3.5-27B and Gemma4-31B"
        source "AI News"
        snippet "A new sparse Mixture-of-Experts LLM with 35B total parameters that runs with only 3B active delivers better coding and vision performance than larger dense models."
        trust "medium"
        seen_on "2026-04-17"
      }
      {
        url "https://x.com/MicrosoftAI/status/2061887500541366489"
        title "Microsoft AI unveils seven new MAI models across reasoning, code, image, speech"
        source "AI News"
        snippet "Microsoft AI releases seven new models, including a data-lineage-first reasoning model. The MAI models cover reasoning, code, image, text-to-speech and transcription."
        trust "medium"
        seen_on "2026-06-03"
      }
      {
        url "https://blog.cloudflare.com/ai-code-review/"
        title "Orchestrating AI code review at scale"
        source "Hacker News"
        snippet "Cloudflare built a CI system that runs up to seven AI code-review agents per merge request and posts a single structured comment, with the architecture and trade-offs laid out."
        trust "medium"
        seen_on "2026-05-30"
      }
    ]
  }
}

// A usable model from an established maker is a release even off the lab list;
// an unknown company's model landing page with extraordinary claims is not.
// Expect Cursor's Composer at 70 or above and SubQ in 35-54.
test score_established_release_vs_unknown_landing_page {
  functions [ScoreArticles]
  args {
    articles [
      {
        url "https://cursor.com/blog/2-0"
        title "Cursor 2.0 adds Composer model with 4x faster coding"
        source "Ben's Bites"
        snippet "Cursor 2.0 releases Composer, a new coding model that runs four times faster, available in the editor today."
        trust "medium"
        seen_on "2026-03-15"
      }
      {
        url "https://subq.ai/"
        title "SubQ: Sub-quadratic LLM for 12-million-token reasoning"
        source "Hacker News"
        snippet "SubQ lets you reason over 12 million tokens in one prompt, at one-fifth the cost of other LLMs. 150 tokens/s, cuts attention compute ~1,000x."
        trust "medium"
        seen_on "2026-05-07"
      }
    ]
  }
}

// Regression for the failure this rubric's traction rule exists to fix: an
// unread Show HN repo and a lab release, judged on the same title-shaped
// evidence. Before traction was passed through, batches like this came back
// with both in the 90s. Expect the repo in the 35-54 band and the release well
// clear of it.
test score_unread_repo_vs_lab_release {
  functions [ScoreArticles]
  args {
    articles [
      {
        url "https://github.com/Gysho/LLMrPro"
        title "Free LLM balancer combines multiple local inference machines with cloud fallback"
        source "Hacker News"
        snippet "LLMrPro balances requests across local inference machines and falls back to the cloud."
        trust "medium"
        traction "4 points, 0 comments on Hacker News"
      }
      {
        url "https://www.anthropic.com/news/claude-sonnet-5"
        title "Claude Sonnet 5: More agentic model with planning and tool use"
        source "Hacker News"
        snippet "Claude Sonnet 5 is available today across the API, with stronger planning and tool use."
        trust "medium"
        traction "612 points, 341 comments on Hacker News"
      }
    ]
  }
}
