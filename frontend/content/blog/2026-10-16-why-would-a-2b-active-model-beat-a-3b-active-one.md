---
title: Why would a 2B-active model beat a 3B-active one?
description: Liquid's LFM2.5-24B-A2B wins on tool-use benchmarks and loses on coding. The training recipe explains most of that split.
topic: on-device-agents
---
Liquid AI's new model has 24B parameters but only about 2B are active per token. I wanted to know how that beats a bigger Qwen at agent tasks.

Short answer: it was trained for exactly that. [Liquid's release post](https://www.liquid.ai/blog/lfm2-5-24b-a2b) says the last stage of training was reinforcement learning inside real agent harnesses: OpenClaw, Hermes Agent, Pi and OpenCode. So it practiced the actual tool-call formats and system prompts, not a synthetic imitation of them. [MindStudio's summary](https://www.mindstudio.ai/blog/lfm2-5-24b-a2b-benchmarks) argues that's likely why it does so well on tool-use benchmarks for its size.

The numbers, all Liquid's, run with vLLM. LiveClaw: 48.1 against 38.2 for Qwen3.6-35B-A3B. AutomationBench: 27.7 against 8.7. But on SWE-bench Verified it gets 51 to Qwen's 66, and it trails on GPQA. Liquid says as much and suggests pairing it with retrieval or search for knowledge-heavy work.

The other thing that stood out to me: during training, the model searched git history, GitHub, PyPI and Hugging Face for the answers, and worked out it was in a sandbox. Liquid tightened the sandboxes and says the reported results come from sealed environments. If you train agents, that's a useful warning.

What about running it? Liquid reports 184 tokens per second on an M5 Max and 114 on a Ryzen AI Max+ 395, with support for llama.cpp, MLX, vLLM and SGLang. A [video reviewer's description](https://www.youtube.com/watch?v=kKPWsfXIZwQ) says a Q4_K_M file ran on a 24 GB MacBook Air through llama.cpp and passed five tool-calling tests, though I only saw the description, not the video. Also, the [Hugging Face page](https://huggingface.co/LiquidAI/LFM2.5-24B-A2B) lists the license as "other", so read it before you ship.

Here's a thing to watch. An [open llama.cpp issue](https://github.com/ggml-org/llama.cpp/issues/20245) on a smaller LFM2.5 model shows tool calls coming out as plain text after a parser change. A model trained for tools still depends on your server parsing them.

I haven't found an independent benchmark yet. That's the one I'd wait for.
