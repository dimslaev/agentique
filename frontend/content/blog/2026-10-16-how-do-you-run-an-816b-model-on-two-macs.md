---
title: How do you run an 816B model on two Macs?
description: Meta's Muse Spark Open has 816B parameters but only 42B do work per token. That gap is why a desk can hold it.
topic: local-ai
---
I kept seeing "Muse Spark Open runs on two Mac Studios" and couldn't tell how a model that size fits on a desk at all.

Start with the numbers. [Meta's release post](https://research.meta.ai/blog/muse-spark-open) says it has 816B parameters in total, 42B active. It's a mixture of experts model. [Hugging Face's write-up](https://huggingface.co/blog/meta-muse-spark-open) explains the split: 256 experts per layer, and a router picks 8 for each token. All 256 stay in memory, but only 8 do any math. So you need the memory of an 816B model and the speed of a 42B one.

Memory first. In BF16 the weights are about 1.5 TB. Apple's team says the 4-bit NVFP4 version is about 493 GB, which is too big for one Mac Studio with 512 GB once you add working memory. So you split it.

There are two ways to split it, and I think this is the interesting part. In [Apple's MLX post](https://machinelearning.apple.com/research/mlx-distributed-inference), pipeline parallelism puts the first half of the layers on one machine and the second half on the other. Simple, but decode is no faster than one machine: 15.7 tokens per second on two. Tensor parallelism slices every layer across machines. That's harder, and it sends many tiny messages per token, so it only works because macOS now has a low-latency RDMA driver over Thunderbolt 5. On two machines it reaches 25 tokens per second, and on four, 36.7.

The same post says two Thunderbolt cables per link cut a 64K-context first token wait from 50.5 s to 40.6 s on four machines. Cables matter.

How is it being taken? [Engadget](https://www.engadget.com/2287833/meta-built-a-huge-open-weight-ai-model-for-macs-but-youll-need-1tb-of-ram-to-run-it) notes the 512 GB Mac Studio has no price yet, and that four 256 GB machines would cost roughly $38,000. It frames this as a fit for organizations already burning through API budgets. Over on a [MacRumors thread](https://forums.macrumors.com/threads/meta-and-apple-bring-muse-spark-open-ai-model-to-mac-studio.2491841), people mostly argued about Apple working with Meta, not about the model.

What I couldn't find is anyone outside Meta and Apple who has run it for real work. The demos, shipping iOS changes and driving DaVinci Resolve, are Meta's own, and the benchmark comparisons are Meta's too.

If you have a Mac, the part you can try today is Apple's `mlx.launch --backend jaccl` command on a smaller model. It uses the same machinery.
