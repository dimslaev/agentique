---
title: Can an AI agent invent a new training method?
description: Epoch hid a recent paper's method and asked two frontier agents to rediscover it. Neither came close, and both oversold what they did.
topic: ai-research-agents
---
I kept seeing "AI can't do research yet" this week and wanted to know what was actually tested.

The test is [Epoch AI's InnovationEval](https://epoch.ai/publications/innovationeval). Take a real method from a January 2026 paper, scrub it from a codebase, and ask an agent to build something that gets the same gains. The method is SDPO, from [an ETH Zurich-led paper](https://self-distillation.github.io/SDPO). The idea is neat: when a coding attempt fails, the error message goes back into the prompt, and the model with that feedback acts as its own teacher. Its next-token guesses are distilled back into the plain model. Normal RL gives one score per attempt. This gives a signal on every token.

The agents didn't know any of that. They got Qwen3-8B, a strong GRPO baseline, 3,000 GPU-hours and no internet.

GPT-5.6 Sol added a term that rewards groups where every rollout already succeeds, since plain GRPO learns nothing from those. Epoch says that's close to prior work. It reached 35% of SDPO's gains if you read the scope generously, 15% once you drop batch size changes that slowed coding training. Claude Fable 5 tried a STaR-like resampling idea that didn't help.

The part I found most interesting is the reporting. Fable's claimed gains came from running many similar runs and submitting the best. Epoch quotes its own note about rerunning "purely to fish for better checkpoints". [TechTimes](https://www.techtimes.com/articles/328913/20261013/ai-research-agents-were-aware-cherry-picking-yet-submitted-misleading-results-studies-show.htm) reports Fable credited itself 43% against about 2% in scope. Sol's workspace notes flagged the same worry, and its write-up didn't mention it.

Caveats, from Epoch itself: one run per model, human review of scope, and newer models (Fable 5.1, GPT-6 Astra) already knew the task. I couldn't find anyone who has tried to replicate it.

If you want to poke at the target, the [SDPO repo](https://github.com/lasgroup/SDPO) is public. And if your own agent reports a win from a sweep, ask how many runs it threw away.
