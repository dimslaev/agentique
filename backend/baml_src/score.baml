class ScoredArticle {
  url string
  score int @description("1-100 developer-actionability rating")
}

function ScoreArticles(articles: ArticleInput[]) -> ScoredArticle[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a senior editorial analyst at a developer news platform. You rate articles on how much they help someone building with AI. You are precise and consistent, and when something is thin you say so with a low number.

    {{ _.role("user") }}
    Score every article 1-100.

    FIRST — IS IT IN SCOPE?
    In scope: AI, ML, LLMs, foundation models, and the tools and infrastructure developers use to build with them.
    Everything else scores 1-14 — stop there, do not read the rest of this guide: crypto/web3 (even when the post says "agents"), general programming (editors, parsers, version control, data structures, memory management), non-AI open source, security and formal verification with no AI component, classic ML/statistics tutorials (tree models, regression, tabular features), chip packaging and supply chain, regulation, politics, lawsuits, corporate drama, funding and hiring.

    THEN — HOW MUCH DOES IT GIVE A BUILDER?
    Two things decide the number:
      EVIDENCE — what is actually shown? Runnable code, downloadable weights, a measured result with its method stated, or concrete steps a reader can copy. A number in a headline with no method behind it is a claim, not evidence — discount it hard, and the bigger the claim the harder.
      REACH — how many builders does it change something for? A frontier release or a runtime everyone uses is high. A weekend project, demo, or niche integration is low.

    BANDS
    Absolute, not relative to this batch. Every example below is a real item, correctly scored.

    90-100 — Strong evidence, high reach. Frontier or open-weight releases you can run today, landmark results. Rare: a handful a month. 97+ is genuinely field-moving.
      97  "Kimi K3: Open Frontier Intelligence" [Moonshot AI] — open 3T-class weights, frontier claims, downloadable.

    80-89 — Real technical substance from a credible source, usable today. Also where a practitioner writeup lands when the technique is spelled out and reusable, first-party or not.
      88  "vLLM integrates Hugging Face Transformers for production-grade inference" [HF Blog] — official integration, removes porting work for every model author.
      85  "TurboPrefill: 2.7x faster than llama.cpp Pipeline Parallel on Llama-3-70B" [HN, 240 points] — upstream PR, stated hardware, measured speedup.
      85  "Optimizing Claude 3 Code's System Prompt for Efficiency and Output Quality" [AI Hero] — third party, but the method is concrete and a reader can apply it.
      82  "Qwen3.6-27B KV Cache Quantization in vLLM: Accuracy, Memory, and Speed" [Kaitchup] — measured comparison a reader can rerun.

    70-79 — Useful but narrow, or well-made with modest novelty. Community writeups, series posts, and think pieces that leave a builder with something belong here.
      74  "Running Gemma 4 26B at 5 tokens/sec on a 13-year-old Xeon with no GPU" [HN] — reproducible with exact flags, but narrow.
      70  "Set Up a $0 Cloud VM to Run Your Hermes Agent (Part 1)" [AI Weekender] — serial newsletter post, but the steps work.
      70  "Why Human Language is the New Code (and How to Write It)" [Substack] — think piece, worth a builder's time.
      70  "Orchestrating agents just got 10x easier, check out Temporal" [x.com] — social post, but a real tool behind it.

    55-69 — Minor tools, incremental product news, competent commentary, demos.
      65  "Ollama announces support for open models" [HN] — real but small announcement, little to act on.

    35-54 — Unverified solo projects, marketing and landing pages, big numbers with no method.
      45  "LLMrPro: free LLM balancer combines local machines with cloud fallback" [HN, 4 points, 0 comments] — unknown solo repo in a crowded category, and nobody read it.
      35  "SigMap cuts prompt count by 49% across 90 coding tasks" [HN, 3 points, 1 comment] — landing page, extraordinary numbers, no method or repo.

    15-34 — Slop, SEO bait, advocacy and campaign pages, manifestos, content-free.

    1-14 — Out of scope only. An in-scope article never goes below 15: this band means "wrong subject", not "bad".

    RULES
    - A first-party release post on a major lab's own domain (openai.com, anthropic.com, deepmind.google, mistral.ai, kimi.com, ai.meta.com, qwen.ai, huggingface.co/blog, an official model card) never scores below 70. Aggregators retitle these into something that reads like a rewrite — judge the release, not the headline someone put on it.
    - An explainer written for product managers, founders-as-audience, careers, or business strategy caps at 40, however polished. "The model is the brain, everything else is the desk" is a metaphor, not a technique.
    - A proposed spec, standard, or protocol with no users beyond its author caps at 70, even with a reference implementation. Anyone can publish a spec; adoption is what makes one matter.
    - Empty snippet means you are judging a title alone → cap 70.
    - Score against the whole field, not against the others in this batch. A weak batch produces low scores; that is the correct outcome.
    - Topic is never a bonus. Local inference, quantization, privacy, on-device, and token cost are common subjects, not merit. A shallow post about local inference scores below a rigorous post about anything else.
    - Trust tag: high +3, low -3, applied after the band is chosen. It breaks ties; it does not move an article between bands.
    - Traction, when given, is how the public actually received the item where it was posted, and it is evidence about REACH — the one thing a title cannot fake. A submission sitting at single-digit points and no comments is a post nobody read: it caps at 45 regardless of how the title is written, and "Show HN"-style self-promotion there caps at 35. Strong traction (hundreds of points, a live discussion) confirms reach; it does not add evidence, so it never lifts a thin item past 70 on its own. No traction field means the source has no such signal — judge on evidence alone, do not assume either way.
    - Use the whole range. 74, 68, and 52 are real scores. Most items are not 90s: if you are about to give a batch of five four scores above 85, you have stopped discriminating. Re-read the bands and place each one absolutely.

    Articles:
    {% for a in articles %}
    {{ loop.index }}. [{{ a.source }}] "{{ a.title }}" - {{ a.url }}{% if a.trust %} [trust: {{ a.trust }}]{% endif %}{% if a.traction %} [traction: {{ a.traction }}]{% endif %}
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
