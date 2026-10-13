---
title: "What is a decision model, and why did everyone ship one?"
description: "OpenAI and Cloudflare both shipped models that answer with a probability instead of text. Here's what that buys you."
topic: decision-models
---
This week OpenAI put its Decisions API into public beta, and Cloudflare released its Clef models. Both are "decision models", and at first I couldn't see how that's different from asking an LLM to reply in JSON.

Here's the idea, as [Simon Willison explained it](https://simonwillison.net/2026/Sep/21/jev) when TypeSafe's Jev started the trend in September. You send some text (the "state") and a few typed questions. The model never writes text back. It returns numbers: the probability that a statement is true, a probability for each option in a list, or a score on a scale you define. You pay for input only.

[Cloudflare's post](https://blog.cloudflare.com/clef-faster-cheaper-multimodal/) shows how one is built. Clef starts from a Qwen model, freezes it, and trains small adapters on top. Instead of generating tokens, it reads the input once and scores every allowed option. The new Clef-omni answers text questions in about 130 ms and takes audio and video too, and [the weights are on Hugging Face](https://huggingface.co/Cloudflare/clef) under Apache 2.0. [OpenAI's version](https://community.openai.com/t/decisions-api-is-now-available-in-public-beta/1403877) runs on GPT-6 Luna and costs $0.10 per million input tokens, with no output charge.

[OpenRouter's comparison](https://openrouter.ai/blog/tutorials/jev-vs-llm-as-a-judge) of Jev with an LLM judge shows why the numbers matter. Asked whether an answer stuck to a passage, the LLM wrote `{"acceptable": false, "confidence": 1}`. Jev returned `0.01`. Both were right about as often (84 and 83 of 88), but every LLM verdict landed near 0 or near 1. Jev put its unsure cases in the middle, and those are the ones you can send to a person. It was also a fifth of the price and a tenth of the latency. On a harder task, checking long summaries against the facts, the LLM judge tracked human experts much better (0.72 against 0.47).

Not everyone is convinced. A [Red Hat benchmark](https://news.ycombinator.com/item?id=49933476) that drew 166 points on Hacker News argued decision models don't reliably beat LLM judges or trained classifiers. In OpenAI's forum thread, one tester found Jev more accurate than the Decisions API on judgment calls, with Luna making about three times as many confident wrong answers. Another simulated a coin that lands heads 70% of the time. Asked as a yes/no question, the API said heads 70% of the time. Asked as a choice, 98%. Their advice: skip choice questions for now.

Simon's worry from September still stands: you get a number and no reason. And OpenAI's forum is still asking how its version works inside.

If you have an LLM call that's really a yes/no or a pick-one, OpenRouter's recipe is a good start: label 50 to 100 real examples, send them to both, and check whether the cases scored 0.9 are right about 90% of the time.
