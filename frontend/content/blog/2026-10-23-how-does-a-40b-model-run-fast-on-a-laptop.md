---
title: How does a 40B model run fast on a laptop?
description: Recursive's Flint reads only 2.5B parameters per token, and a 4-bit output layer is part of the trick. Here is what people saw when they ran it.
topic: local-coding-models
---
Recursive's new coding model, Flint, has a number I couldn't make sense of: 40 billion parameters, but a claimed 125+ tokens per second on a MacBook Pro. How?

The answer is in "mixture of experts" (MoE). The model holds many small expert networks, and for each token a router picks a few. Flint stores 40B parameters but uses about 2.5B per token. Generating text on a laptop is mostly limited by how much memory you read per token, so reading 2.5B instead of 40B is the speedup.

The part I think is really cool is the [quantization](https://recursive.com/updates/introducing-recursive-flint). Quantizing means storing weights in fewer bits. Normally people leave the output layer, `lm_head`, at higher precision. Recursive quantized it to 4 bits anyway, because with only 2.5B active parameters the output layer is a big share of what gets read each token. To win back accuracy they trained the 4-bit model on its own sampled answers, with the 16-bit model as teacher. They say the final NVFP4 model lands within 0.7 points of 16-bit on their benchmarks. All of this was designed by their own automated research system, which is their claim and I can't check it.

How does it hold up? [MarkTechPost's write-up](https://www.marktechpost.com/2026/10/21/recursive-flint-local-coding-model) reports SWE-bench Verified at 74.2% but Terminal-Bench 2.1 at 54.9%, against 73.0% for a dense Qwen 3.8 model. So it is fast, and it trails the strongest dense models on terminal tasks.

One person [tried it on a 24 GB MacBook Air](https://www.youtube.com/watch?v=Ne1nEO6L-kE) with a 3-bit 14.5 GB file. It passed four Python tasks and three of four other languages (Rust failed). Speed fell from 52 to 17 tokens per second as context grew from 1k to 65k, well below Recursive's number, which was measured on a different chip and engine at short context. A [Hacker News commenter](https://news.ycombinator.com/item?id=50183678) called the quality roughly that of a 27B Qwen at much higher speed, before trying it. Recursive itself says to split complex tasks and stay under 256k tokens.

If you have 24 to 48 GB of memory, it's worth pulling the weights and timing it at your own context length. Nobody I read has compared it on a real long-running agent session yet.
