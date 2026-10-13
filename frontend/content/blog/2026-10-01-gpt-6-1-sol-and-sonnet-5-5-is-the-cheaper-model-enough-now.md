---
title: "GPT-6.1 Sol and Sonnet 5.5: is the cheaper model enough now?"
description: "Both claim near-flagship scores for a fraction of the cost. What that number means, and what people found."
topic: model-releases
---
This week OpenAI and Anthropic each shipped a mid-tier model with the same pitch: nearly as good as our top model, for much less. I wanted to know what "much less" means, and whether anyone has found what you give up.

[GPT-6.1 Sol](https://openai.com/index/introducing-gpt-6-1-sol/) is an update to GPT-6 Sol, which came out only a week earlier. OpenAI says it nearly matches GPT-6 Astra, their top model, at a fifth of Astra's token price: $2 per million input tokens, $10 per million output. [Claude Sonnet 5.5](https://www.anthropic.com/claude-sonnet-5-5) costs the same, half the price of Opus 5.5, and lands within about two points of Opus on several of Anthropic's tests.

The idea that makes these claims readable is cost per task. That's the token price times how many tokens the model uses to finish the job, and the effort setting decides most of the second number. Higher effort means longer thinking, more tokens, and usually a higher score. Both posts chart score against cost per task at each effort level. Sonnet 5.5 has the same token price as Sonnet 5 but, Anthropic says, costs up to 30% less per task because it needs fewer tokens.

The part I found surprising: more effort isn't always better. In a footnote, Anthropic says Sonnet 5.5 scored lower at Max than at Xhigh on one coding benchmark, because at Max it more often split the work across many subagents, which caused a timeout or edits outside the task. [Simon Willison watched](https://simonwillison.net/2026/Sep/22/opus-and-sol-and-luna) Opus 5.5 at max think about a pelican on a bicycle until it hit the 128,000 output token limit without answering, twice, at $2.56 and nearly 20 minutes each. His [pelicans for GPT-6.1 Sol](https://simonwillison.net/2026/Sep/29/hn-49898129/) came back "not notably different" from the rest of the GPT-6 family.

So what do you lose? [Sonar ran GPT-6 Sol and Astra](https://www.sonarsource.com/blog/open-ai-gpt-6-sol-evaluation/) through the same coding benchmark. Sol passed slightly fewer tests (83.09% against 85.85%) and wrote 27% less code, but that code had more vulnerabilities: 137 against 117. That was the previous Sol, though. Nobody I read has run the same test on 6.1 yet.

Some people don't trust the charts at all. On Hacker News, [one commenter said](https://news.ycombinator.com/item?id=49897054) GPT-6 Sol looked great on benchmarks but was no better than GPT-5.6 Sol in practice, and worse for code review.

If you want to try one, take a task you already run and compare the cheaper model at low and medium effort with what you use now: cost per task, and whether the output passes your review. If you call Sonnet with thinking off, you'll need to switch to the new `between_tools` setting before moving to 5.5.
