class ScoredArticle {
  url string
  score int @description("1-100 developer-actionability rating")
}

function ScoreArticles(articles: ArticleInput[]) -> ScoredArticle[] {
  client Nvidia
  prompt #"
    {{ _.role("system") }}
    You are a senior editorial analyst at a developer news platform. Your job is to evaluate articles for relevance and actionability for AI builders. You are precise, consistent, and ruthless about filtering noise. Most of what crosses your desk is promotional or derivative, and you say so with a low number.

    {{ _.role("user") }}
    Score every article on a 1-100 scale.

    STEP 1 - SCOPE CHECK (apply first, before anything else):
    Is this about AI, ML, LLMs, foundation models, or the tools and infrastructure developers use to build with them?
    - NO → score 1-14 and move on. Do NOT apply the rest of this guide.
    - Out of scope: crypto/web3/blockchain (even when the post says "agents"), text editors, parsers, version control, data structures, memory management, general programming tutorials, non-AI open source, formal verification and security work with no AI component, classic ML/statistics tutorials (tree models, regression, tabular feature engineering), chip packaging and supply-chain analysis, regulation, politics, lawsuits, corporate drama, funding and hiring news.

    STEP 2 - SOURCE INTEGRITY CHECK (apply second):
    Decide what kind of thing you are looking at, because it caps the score.
    - Social-media repost (x.com, reddit.com, threads) → cap 55, whatever it claims.
    - Marketing or landing page with no repo, paper, or method → cap 45.
    - Personal-brand newsletter post: first-person build story, "I built X in 30 minutes", "Part 1/2/3" series, listicle ("8 ways to…", "7 examples of…"), a metaphor or think piece, a post whose payoff is a downloadable prompt → cap 45.
    - Explainer written for a non-engineering audience — product managers, founders-as-audience, careers, business strategy — however polished → cap 40. "The model is the brain, everything else is the desk" is a metaphor, not a technique.
    - Content-farm rewrite of someone else's announcement → cap 65.
    - Advocacy, manifesto, or campaign page → cap 35.
    - Review or "deep dive" into somebody else's repo, written by a third party → cap 50.
    - A proposed spec, standard, protocol, or manifesto with no users beyond its author → cap 40, even when a reference implementation exists. Anyone can publish a spec; adoption is what makes one matter.
    A high trust tag does not lift these caps. A newsletter that is mostly a link roundup is still a roundup.

    One floor, applied the same way: a first-party release post on a major lab's own domain (openai.com, anthropic.com, deepmind.google, mistral.ai, kimi.com, ai.meta.com, qwen.ai, huggingface.co/blog, an official model card) never scores below 70. Aggregators often retitle these into something that reads like a rewrite — judge the release, not the headline someone put on it.

    STEP 3 - SCORE ON TWO AXES (only for what survived):
    Audience: developers, founders, and tech leaders building with AI who want to ship faster.

    Axis A - EVIDENCE. What is actually shown?
    - Strong: measured numbers with the setup stated, working code you can run, weights you can download, a reproducible benchmark, an upstream patch.
    - Medium: a clear method described without full results, an official release page, a well-argued engineering writeup.
    - Weak: percentages with no method, a claim in a headline, a promise that the next post will show it, a summary of a summary.

    Axis B - CONSEQUENCE. How many builders does it change anything for, and how much?
    - High: a frontier or open-weight model release, a framework or runtime everyone uses, a technique that removes a real cost, a security finding in software people run.
    - Medium: a solid tool in a crowded category, a good benchmark, a production writeup from a company with real scale.
    - Low: a one-person weekend project, a hobby experiment, a demo, a niche integration, restated common knowledge.

    Bands (evidence × consequence, absolute — not relative to this batch):
    - 90-100: strong evidence AND high consequence. Frontier or open-weight releases you can run today, landmark results. Rare: expect a handful a month. 97+ is reserved for a genuinely field-moving release.
    - 80-89: strong evidence, medium-to-high consequence. Real technical substance from a credible source, usable today.
    - 70-79: medium evidence, medium consequence. Useful but narrow, or good writing with modest novelty.
    - 55-69: minor tools, incremental product news, competent commentary, demos.
    - 35-54: unverified solo projects, thin newsletter posts, marketing, third-party rewrites.
    - 15-34: slop, SEO bait, social reposts, advocacy, content-free.
    - 1-14: reserved for step 1 only. An article about AI never scores below 15, however worthless it is — that band means "wrong subject", not "bad".

    CALIBRATION RULES:
    - The median in-scope article is around 55. If you are scoring most of a batch above 80, you are wrong.
    - Score each article against the whole field, not against the others in this batch. A weak batch produces low scores; that is the correct outcome.
    - Do not cluster on round numbers. 74 and 68 and 52 are real scores. Avoid defaulting to 85, 90, 93, 95.
    - Topic is never a bonus. Local inference, quantization, privacy, on-device, and token-cost are common subjects, not merit. A shallow post about local inference scores below a rigorous post about anything else.
    - Numbers are evidence only when the method behind them is visible: the setup, the workload, the hardware, or a repo. The same number in a headline with nothing behind it is a claim — discount it hard, and the bigger the claim, the harder. "Pruned RAG context by 68% while preserving 96% recall", with the technique described, is a real result and belongs at 80; "cuts tokens by 97%" on a landing page belongs at 35.
    - If the snippet is empty you are judging a title alone → cap at 70, because you cannot see whether anything is behind it.
    - Trust tag: high +3, low -3, applied after the band is chosen. It breaks ties; it does not move an article between bands.

    WORKED EXAMPLES (real items, correctly scored):
    - "Kimi K3: Open Frontier Intelligence" [Moonshot AI] → 97. Open 3T-class weights, frontier claims, downloadable.
    - "vLLM integrates Hugging Face Transformers for production-grade inference" [HF Blog] → 88. Official integration that removes porting work for every model author.
    - "TurboPrefill: 2.7× faster than llama.cpp Pipeline Parallel on Llama-3-70B" [HN] → 85. Upstream PR, stated hardware, measured speedup.
    - "Qwen3.6-27B KV Cache Quantization in vLLM: Accuracy, Memory, and Speed" [Kaitchup] → 82. Measured comparison a reader can rerun.
    - "Running Gemma 4 26B at 5 tokens/sec on a 13-year-old Xeon with no GPU" [HN] → 74. Reproducible with exact flags, but narrow.
    - "Ollama announces support for open models" [HN] → 55. Real but small announcement, nothing to act on.
    - "LLMrPro: free LLM balancer combines local machines with cloud fallback" [HN] → 45. Unknown solo repo in a crowded category.
    - "SigMap cuts prompt count by 49% across 90 coding tasks" [HN] → 35. Landing page, extraordinary numbers, no method or repo.
    - "Set Up a $0 Cloud VM to Run Your Hermes Agent (Part 1)" [AI Weekender] → 25. Serial newsletter filler.
    - "Protect your right to run local AI" [HN] → 30. Campaign page; nothing technical.
    - "Why Human Language is the New Code (and How to Write It)" [Substack] → 20. Think piece with no content.
    - "NEAR Launches General Availability of Confidential Intents via 1Click Swap API" [x.com] → 12. Crypto, out of scope.

    Articles:
    {% for a in articles %}
    {{ loop.index }}. [{{ a.source }}] "{{ a.title }}" - {{ a.url }}{% if a.trust %} [trust: {{ a.trust }}]{% endif %}
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

// Regression: newsletter filler and advocacy pages used to score 95 because
// they mentioned local inference and agents. Both must land below 45.
test score_newsletter_slop {
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
      }
      {
        url "https://github.com/ggml-org/llama.cpp/pull/24219"
        title "TurboPrefill: 2.7x faster than llama.cpp Pipeline Parallel on Llama-3-70B"
        source "Hacker News"
        snippet "TurboPrefill implements intra-prompt pipeline scheduling for multi-GPU prefill. On Llama-3-70B it runs 2.7x faster than llama.cpp pipeline parallel."
        trust "medium"
      }
    ]
  }
}
