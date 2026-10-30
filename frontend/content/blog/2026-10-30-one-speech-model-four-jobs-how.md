---
title: One speech model, four jobs. How?
description: NVIDIA's Nemotron 3.5 Transcribe does transcripts, speaker labels, translation and audio Q&A from one checkpoint, steered by a text prompt.
topic: speech-models
---
I used to think of speech-to-text as one job: audio in, words out. Then you want to know who said what, or have it in English, or spell "metformin" right, and you end up with three more tools. NVIDIA's new Nemotron 3.5 Transcribe tries to do all of that with one model and a sentence of instruction.

Here is the idea, from [NVIDIA's post](https://huggingface.co/blog/nvidia/nemotron-transcribe-granary). You give it a recording and a prompt like "Transcribe this recording and label each speaker", or "Translate this audio into English", or "What decisions were made in this meeting?" The prompt picks the output. It transcribes 40 languages, translates 31, labels speakers in 13, and takes recordings up to an hour with up to 8 speakers.

It is a 30B mixture-of-experts model with about 4B active at a time. That means only a small slice of the network runs for each step, which is how it stays affordable to serve.

The part I find most useful is domain words. You can put a list in the prompt, like `HbA1c, metformin`, and tell it to use them only when the audio supports it. NVIDIA's medical case study found a better prompt cut word error rate from 30.8% to 23.8%, and fine-tuning brought it to 11.8%. On held-out speakers, fine-tuning cut it by 45.8% against the best prompt. These are NVIDIA's numbers on an open benchmark of Indian medical speech.

The leaderboard claims are strong too: first among open-weight models on the Open ASR Leaderboard for English, at 5.33% average error. I could only read NVIDIA's account of those.

What have outside people said? [Cobus Greyling](https://cobusgreyling.substack.com/p/nvidia-nemotron-35-transcribe) walks through the same prompt patterns and points to a real limit: the audio, your prompt and the answer all share one 64,000-token budget, so a long recording with a heavy prompt leaves less room for output. He also shared a [notebook repo](https://github.com/cobusgreyling/nemotron-3.5-transcribe) with seven prompt patterns. It is small, with 1 star, so treat it as a starting point.

Two caveats from NVIDIA itself: it is built for recorded audio, not live streaming, and you should spot-check names and speaker changes. I did not find an independent test of the speaker labels yet.

If you have a few real recordings with tricky vocabulary, try the same file with and without a term list and see which words change.
