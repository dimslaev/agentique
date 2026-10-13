---
title: "What can you do with one embedding for text, images and audio?"
description: "EmbeddingGemma 2 puts every kind of input in the same 768 numbers, and you can throw two-thirds of them away."
topic: embeddings
---
Google released EmbeddingGemma 2 this week, and the headline is that it puts text, code, images, video and audio "in a shared embedding space". What does that let you build?

Quick refresher: an embedding model turns an input into a list of numbers, here 768 of them, so that similar things get similar lists. Search then means "find the stored lists closest to my query's list". With a text-only model like the first EmbeddingGemma, images needed a second model, and the two sets of numbers couldn't be compared.

[EmbeddingGemma 2](https://deepmind.google/blog/embeddinggemma-2-an-open-lightweight-multimodal-embedding-model/) sends everything into the same 768 numbers. A text query can find a photo or an audio clip directly. [MindStudio tried this](https://www.mindstudio.ai/blog/run-embeddinggemma-2-locally) with six images and six text queries, and every query found its image, including "something delicious" matching a picture of curry. The [model card](https://huggingface.co/google/embeddinggemma-2) has an example: one product listing with text, two photos and a video becomes a single vector you can compare against "waterproof shoes for trail running".

It's built in pieces: a 270M text model, plus vision and audio encoders you only load if you need them. Quantized and text-only, it needs about 191MB of RAM on a Pixel phone. On text alone it scores about the same as the first EmbeddingGemma (61.36 against 61.15); the jump is on code (78.68, up from 68.76).

The other trick is Matryoshka embeddings. The model is trained to pack the most important information into the first numbers, so you can keep only the first 256 and store a third as much. The card's table shows the cost: down to 256, scores barely move. At 128, text holds up but the multimodal score drops from 59 to 46. MindStudio's six image matches stayed the same at 256.

The model card has two warnings I'd have missed. After you cut a vector down, you have to re-normalize it, or rankings get worse with no error. And don't run it in float16: you get NaNs or quietly broken vectors.

[Simon Willison pointed out](https://simonwillison.net/2026/Oct/6/hn-49983751/) why an open license like Apache 2.0 matters especially for embeddings: you might store millions of vectors, and if a hosted model is retired you have to pay to recompute all of them. Open weights mean you can always run the old one.

Two things I'm unsure about. The card also says deployments must follow Gemma's Prohibited Use Policy, and I don't know how that sits next to Apache 2.0. And nobody I read has tried audio search on real recordings yet.

If you have a folder of photos or screenshots you can't search, it's a small model to try: embed them and a few text queries at 256 dimensions, and see what comes back.
