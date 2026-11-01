---
title: Can you remove a model's hacking skills?
description: Moonshot says it cut cyber data from Kimi K3.1 Pro before the open-weight release. Here is what that did, and what people think of the model.
topic: open-weight-cyber
---
I kept seeing Kimi K3.1 Pro this week and assumed it was one more model with a benchmark table. Then I read the part of the announcement about cybersecurity, and that was the interesting bit.

First, the basics. [Moonshot's post](https://www.kimi.ai/blog/kimi-k3-1-pro) says K3.1 Pro is a post-trained Kimi K3, a 3T-class model with a 1M-token context window. It is on their API now. The weights are promised "by Nov 4", so they are not out yet.

Here is the idea I think is clever. Moonshot says that while they scaled up post-training, the model got steadily better at finding vulnerabilities. They traced it to two places: cyber-related text mixed into the general mid-training data, and cyber tasks sitting in the reinforcement learning (RL) environments. For the open-weight build they removed both.

Then they measured it. On xdev-bench-hard, their own benchmark of exploiting real bugs in things like the Linux kernel and Node.js, the checkpoint without the removals solved 90.5% of problems at pass@3. The final model solves 81.0%.

So removal did something, but not that much. Moonshot says as much: general coding skill still leaks into cyber tasks. This is their own benchmark and their own comparison, and I haven't seen anyone outside Moonshot repeat it.

Their stated reasoning is that open weights should not push the public frontier of offensive cyber ability, but should still help defenders audit code they maintain. You can disagree with that bet. I'd like to see someone else test it.

How is the model being received? [Simon Willison](https://simonwillison.net/2026/Oct/23/kimi-k31-pro/) noted that Artificial Analysis scores it at 55, behind only Claude Opus 5.5 at 58, and that it costs $2 per million input tokens and $10 per million output tokens. He only ran pelican drawings, so that is a price and a leaderboard, not a real test.

On [Hacker News](https://news.ycombinator.com/item?id=50213202), one commenter paid for the $40 plan. They call the output quality solid, but say they still hit the 5-hour rate limit quickly, and rank it fourth behind Opus 5.5, Astra and Argon. That is one person's tier list. The [main thread](https://news.ycombinator.com/item?id=50212246) is worth a look for more, though the page would not load for me, so I only saw search snippets.

If you plan to self-host once the weights land, the thing to watch is whether outside groups reproduce that 90.5% to 81.0% drop.
