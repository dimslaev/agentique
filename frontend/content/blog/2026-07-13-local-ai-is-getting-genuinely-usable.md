---
title: "Your GPU budget is behind, not the models"
description: "A 7MB embedding model running in the browser, a 1-petaflop desktop chip, and a GPT-2 built from scratch in pure C."
slug: local-ai-is-getting-genuinely-usable
topic: local-ai
date: 2026-07-13
articles:
  - https://teodoracoach.substack.com/p/the-30-minute-ai-agent-that-never
  - https://ternlight-demo.vercel.app/
  - https://github.com/JustVugg/nanoeuler
  - https://www.iroh.computer/blog/mesh-llm
  - https://nvidianews.nvidia.com/news/nvidia-microsoft-windows-pcs-agents-rtx-spark
  - https://huggingface.co/spaces/webml-community/gemma-4-webgpu-kernels
---

For a long time, "local AI" meant a smaller model that did noticeably worse.
Everything I read this week points at that gap closing faster than I
expected.

[Ternlight](https://ternlight-demo.vercel.app/) is a 7MB embedding model — 5MB
in its mini form — that ships as an npm package and generates embeddings in
about 5 milliseconds on a CPU, no server involved. And Google's
[Gemma 4 E2B demo](https://huggingface.co/spaces/webml-community/gemma-4-webgpu-kernels)
runs entirely in the browser through WebGPU at around 255 tokens a second on
an Apple M4 Max. "Runs in a browser tab" used to be the caveat. Now it's
just a reasonable way to ship something.

The hardware side is catching up too. Nvidia's
[RTX Spark](https://nvidianews.nvidia.com/news/nvidia-microsoft-windows-pcs-agents-rtx-spark)
is a 1-petaflop chip built for on-device agents on Windows PCs, with up to
128GB of unified memory. Running a real model locally is turning into a
budget question, not a "can this even be done" question. And if you want to
understand what's actually happening under the frameworks you use every
day, [NanoEuler](https://github.com/JustVugg/nanoeuler) builds a GPT-2-scale
model from scratch in pure C and CUDA — hand-written tokenizer, training
loop, all of it. I learned more skimming that repo than I expected to.

Two more worth mentioning. [Mesh LLM](https://www.iroh.computer/blog/mesh-llm)
pools GPUs you already own into a single OpenAI-compatible API, so you can
skip the inference bill entirely by using hardware sitting in your own
house. And there's a [walkthrough for building a local agentic assistant](https://teodoracoach.substack.com/p/the-30-minute-ai-agent-that-never)
with OpenClaw, Gemma 2, and Docker — free web search included, everything
staying on your machine. It's a reasonable weekend project if you want to
find out what a fully private setup actually costs you in capability.

My honest read: the models are ready before most people's hardware is. If
you've been putting off going local, that's the part worth reconsidering
first.
