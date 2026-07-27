---
title: "Inference got faster without new hardware"
description: "4-bit diffusion models on GPUs from 2018, a router that fills your idle machines before the cloud, and a voice agent that cut latency 44% by going local."
slug: inference-got-faster-without-new-hardware
topic: inference-optimization
date: 2026-07-27
articles:
  - https://huggingface.co/blog/nunchaku-diffusers
  - https://github.com/Gysho/LLMrPro
  - https://deepmind.google/models/gemma/gemmaverse/cue-ai/
---

A 4-bit image model that runs on a GPU from 2018. A router that treats
your own idle desktop as a cheaper model tier than the cloud. A voice
agent that got faster by reaching for a smaller model instead of a bigger
one. Three different answers this week to the same question — where's the
free performance sitting unused right now, before you reach for a bigger
card or a fatter API bill.

[Nunchaku](https://huggingface.co/blog/nunchaku-diffusers) is now a
first-class citizen in Hugging Face's Diffusers library — you load a
Nunchaku checkpoint with a plain `from_pretrained()` call, no custom
pipeline, no local CUDA build. What it actually does is run diffusion
transformers (Stable Diffusion, FLUX-style models) at 4-bit precision
without the usual quality collapse. The trick, from MIT HAN Lab's SVDQuant
technique underneath it, is that 4-bit quantization normally breaks on
outlier values in weights and activations; SVDQuant peels those outliers
into a small 16-bit side branch and only quantizes the residual, keeping
the hard part of the math high-precision. The team's own benchmarks claim
up to 3x faster inference and roughly 50% less VRAM than a 16-bit baseline
— and the part I'd actually use is that INT4 checkpoints run on
Turing/Ampere/Ada cards going back to 2018, not just this year's Blackwell
GPUs, where the faster NVFP4 variant is restricted. Those numbers are the
vendor's own, so take the exact multiples with a grain of salt, but "runs
image generation locally on a 4090 instead of renting an A100" holds up
even at half the claimed speedup.

[LLMrPro](https://github.com/Gysho/LLMrPro) is a much smaller, rougher
project solving an adjacent problem: it's a self-hosted router that gives
you one OpenAI-compatible endpoint, then serves each request from a pool of
machines you already own — desktops, workstations, whatever's idle — via
LM Studio, Ollama, vLLM, llama.cpp, or its bundled MLX engine on macOS,
falling back to a configured cloud provider only when nothing local can
handle the request, no inbound ports required. It's the same instinct as
Nunchaku's — extract more from hardware you already own — applied at the
fleet level instead of the model level. I'd flag it as early-stage rather
than a batteries-included alternative: the repo shows 7 stars and one fork,
closer to "one person's homelab setup, open-sourced" than a hardened tool.
Worth watching if you've got spare machines and hate your API bill, not
worth betting production traffic on yet.

[Cue](https://deepmind.google/models/gemma/gemmaverse/cue-ai/), a
desktop voice agent, took the same idea to its logical endpoint: stop
calling the cloud at all for a task a small model can do. Cue switched
dictation and text-polishing to a locally-run Gemma 4 E4B and, per
Hugging Face and Cerebras's write-up on the integration, median latency
dropped from 876ms to 488ms — a 44% cut — while marginal inference cost
went to zero. The team reports feature usage rose 30% once the lag was
gone, which tracks: dictation is exactly the kind of interaction where a
half-second stall is the difference between using a feature and giving up
on it. This is a single vendor's account of its own product, so treat the
specific percentages as a best case — but the underlying bet, that a small
on-device model beats a bigger one round-tripping to a server for a
latency-sensitive task, is one I'd try before reaching for a hosted API on
anything voice-shaped.

What ties them together is a refusal to assume the bottleneck is a bigger
GPU. If I were optimizing inference this week, I'd start with whichever one
matches the bottleneck I actually have: Nunchaku if it's VRAM, LLMrPro if
it's idle hardware and a cloud bill, Cue's approach if it's latency on a
task small enough for a 4B model to handle.
