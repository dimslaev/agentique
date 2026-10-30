---
title: Where does GPT-6.1 Terra fit?
description: OpenAI's mid-priced model is pitched at computer use and vision. Here is what it claims, what OpenAI's own engineer says, and where people push back.
topic: gpt-6-1-terra
---
OpenAI now has four models in one family, and I couldn't tell where the new one, GPT-6.1 Terra, was supposed to sit. So I read what OpenAI says and what people said back.

The short version from [OpenAI's post](https://openai.com/index/introducing-gpt-6-1-terra): Terra is a fast, cheaper model aimed at visual reasoning and computer use, meaning a model that looks at a screen and clicks through forms and apps. The price is $1 per million input tokens and $5 per million output, according to [Simon Willison](https://simonwillison.net/2026/Oct/26/gpt-61-terra/). He puts that at almost half of GPT-5.6 Terra and GPT-6.1 Sol, and around 10x GPT-6 Luna.

The headline number is on Agents' Last Exam, a set of professional tasks like turning architectural drawings into a 3D model. At medium reasoning effort, OpenAI says Terra scores 15 points above GPT-5.6 Terra at about a third of the cost. It also says Terra matches GPT-6 Astra there at a tenth of the per-token price. Note that this is OpenAI's own run.

Why does that matter for computer use specifically? Those jobs are repetitive. You may click through thousands of forms, so a cheaper model that is good enough adds up fast.

The most useful advice I found came from an OpenAI person. Simon quotes Ted Sanders, who wrote on Hacker News that Terra is probably better than Astra and Sol at technical communication, similar on vision and computer use but much faster, and a bit worse on most other things. He calls it a nice midrange option, not a bombshell.

Reactions in the [launch thread](https://news.ycombinator.com/item?id=50248124) split fast. One commenter read the charts as roughly Opus 5.5 level for a quarter of the price. Another replied that at max effort it scores about 50% on Terminal-Bench against Opus 5.5's 70%, which is a different picture for coding. Both were reading the same charts, so the answer depends on your task.

There is also a theory in an [earlier thread on Sol](https://news.ycombinator.com/item?id=49896586) that the naming reshuffled because nobody used the old Terra. I can't confirm that one, and I'd treat it as a guess.

If you run browser or form-filling agents, the cheap test is to run your own 20 tasks through Terra and Sol and compare the cost per finished task. Nobody I read has published that yet.
