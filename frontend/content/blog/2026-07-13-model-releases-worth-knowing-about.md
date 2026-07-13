---
title: "Open weights stopped being the compromise option"
description: "Claude Sonnet 5, GPT-5.6, and an open-weight model with a 1M-token context that runs on any Nvidia GPU."
slug: model-releases-worth-knowing-about
topic: model-releases
date: 2026-07-13
articles:
  - https://kaitchup.substack.com/p/dspark-and-nvidias-qwen36-nvfp4-models
  - https://openai.com/index/gpt-5-6/
  - https://www.anthropic.com/news/claude-sonnet-5
  - https://sub.thursdai.news/p/open-source-ai-just-had-its-2nd-deepseek
  - https://developer.nvidia.com/topics/ai/nemotron
  - https://notegpt.io/nano-banana-2-lite
---

What struck me about this week's model releases wasn't any single one of
them — it's how differently each lab is choosing to compete. Some are
chasing reasoning, some are chasing cost, and a couple are just giving the
weights away.

[Claude Sonnet 5](https://www.anthropic.com/news/claude-sonnet-5) leans
agentic: planning, browser and terminal use, running on its own for longer
stretches, while matching Opus 4.8's performance at a lower price. If your
work is more "let it run" than "chat back and forth," I'd put this one on
your list to actually test, not just read about.
[GPT-5.6's architecture details](https://openai.com/index/gpt-5-6/) landed
the same week, and if you're choosing between the two for something new,
it's worth reading both before you pick.

The part I found genuinely interesting, though, was open weights.
[GLM 5.2](https://sub.thursdai.news/p/open-source-ai-just-had-its-2nd-deepseek)
is being called open source's second "DeepSeek moment" — not because a
closed lab panicked, but because it's just competitive, on its own merits.
Nvidia's [Nemotron 3 Ultra](https://developer.nvidia.com/topics/ai/nemotron)
backs that up with a hybrid transformer-Mamba design, a million-token
context window, open weights, and it runs on any Nvidia GPU you already
have. A year ago, "open weight" meant "smaller and a bit worse." I don't
think that's true anymore.

On the smaller, cheaper end,
[DSpark and Nvidia's Qwen3.6 NVFP4 models](https://kaitchup.substack.com/p/dspark-and-nvidias-qwen36-nvfp4-models)
both target high-throughput inference with 4-bit precision — worth a look if
your actual problem is the inference bill, not raw capability. And
[NanoBanana-2 Lite](https://notegpt.io/nano-banana-2-lite) generates a
thousand images almost instantly, trading some polish for speed. Fine for
prototyping, not what I'd reach for on a final render.

If you've been defaulting to the biggest closed model for everything out of
habit, this is the week to actually run Nemotron 3 Ultra or GLM 5.2 against
your own workload. I don't think you'll be disappointed, and you might save
yourself some money finding out.
