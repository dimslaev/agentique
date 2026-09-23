# Curation regression set

70 articles hand-labelled on 2026-09-16 from a stratified sample across six
months of the feed: every article kind at three score bands, the loudest
publishers, 16 rejects the pipeline had dropped, and 7 articles the reader named
as what they want. 27 love, 22 fine, 21 noise.

Run the rubric in `SKILL.md` against these before letting the agent run
unattended, and after any change to the rubric.

**Bar:** noise kept under 3 of 21, loved dropped under 3 of 27, and every
coverage case (below the main table) landing as labelled. A kept article
is one scoring 65 or above (55 for a high-trust individual publisher, which is
the threshold the feed used); the number matters less than the ordering, so
check that the loved articles sit above the noise rather than that any single
score matches.

Columns: **was** is the score the deployed rubric gave it; **new** is the median
of three runs of the rewritten rubric plus URL limits. `-` where a run did not
return a verdict. `kind` of `rejected` means the pipeline had already turned it
down.

| label | kind | publisher | was | new | article |
|---|---|---|---|---|---|
| love | model | The Batch | 96 | 86 | [Nvidia Nemotron 3 Ultra: Open-weight LLM with transformer-mamba archit](https://developer.nvidia.com/topics/ai/nemotron) |
| love | product | NVIDIA Developer | 92 | 55 | [NIM-Layer Optimizations Enable Efficient LLM Scaling Across GPUs in Ne](https://developer.nvidia.com/blog/how-full-stack-nim-optimizations-deliver-2-5x-more-users-on-nemotron-3-ultra/) |
| love | product | Mistral AI Blog | 86 | 78 | [Agentic Search. More accurate and efficient results from your AI syste](https://mistral.ai/news/agentic-search/) |
| love | announcement | Google DeepMind Blog | 86 | 84 | [Gemma 4 open model family: 2B, 4B, 26B MoE, 31B dense](https://deepmind.google/blog/gemma-4-byte-for-byte-the-most-capable-open-models/) |
| love | announcement | Loop Engineering | 85 | 45 | [Complete Fable 5 playbook with Claude prompting patterns](https://linas.substack.com/p/prompting-claude-fable-5-guide) |
| love | repo | There's An AI For That | 85 | 78 | [LMCache: Multi-tier LLM Cache Reducing Time-to-First-Token 10x](https://github.com/LMCache/LMCache) |
| love | blog | Hacker News | 85 | 45 | [How a Model-Centric Compiler Reduces AI Agent Token Consumption by Opt](https://vivekhaldar.com/articles/compiling-an-ai-agent-skill/) |
| love | announcement | Simon Willison | 85 | - | [Google releases Gemini 3.8 Live speech-to-speech models](https://simonwillison.net/2026/Sep/15/gemini-live/) |
| love | paper | The Batch | 85 | 73 | [BAGEL-7B: Multimodal Model for Staged Image Generation (arXiv Paper)](https://arxiv.org/abs/2505.14683) |
| love | product | Ben's Bites | 84 | 73 | [Firecrawl Research Index: Specialized Agent Index for ArXiv Queries](https://www.firecrawl.dev/blog/research-index-launch) |
| love | product | TLDR AI | 84 | 78 | [Self-Hosted Machines for Cursor's Cloud-Agent Infrastructure Control](https://cursor.com/blog/self-hosted-machines) |
| love | blog | JetBrains | 82 | 62 | [Building LLM Applications with Rig: Practical Rust AI Development Insi](https://blog.jetbrains.com/rust/2026/09/09/rust-ai-in-practice/) |
| love | announcement | Google DeepMind Blog | 82 | 85 | [Gemini Omni 1.1 Flash Expands Developer Controls and Introduces Genera](https://deepmind.google/blog/gemini-omni-1-1-flash-lets-you-build-with-more-control/) |
| love | repo | Hacker News | 82 | 73 | [PyScrappy: AI-Optimized Web Scraping Toolkit with MCP Agent Integratio](https://github.com/mldsveda/PyScrappy) |
| love | announcement | DeepSeek | 78 | 82 | [Introducing DeepSeek-V4.1-Flash: smarter, faster, more efficient.](https://www.deepseek.com/news/deepseek-v4-1-flash) |
| love | product | Ben's Bites | 73 | 45 | [Factory 2.0: Platform for AI-Driven Software Development Pipelines](https://factory.ai) |
| love | blog | Sonar | 73 | 85 | [The context tax: why your coding agent reads the same 600 lines 400 ti](https://www.sonarsource.com/blog/stop-the-context-tax/) |
| love | blog | Machine Learning Pills | 73 | 48 | [When a Smaller Model Reduces Costs and Runs Deployment Constraints Bet](https://mlpills.substack.com/p/issue-139-small-language-models-when) |
| love | repo | Pointer | 73 | 78 | [BrowserSkill](https://github.com/Tencent/BrowserSkill) |
| love | model | The Rundown AI | 72 | 75 | [Moonshot lets history's largest open model loose](https://www.therundown.ai/p/moonshot-lets-history-largest-open-model-loose) |
| love | blog | AI Weekender | 71 | 58 | [Prompt vs RAG vs Fine-Tuning: Which Fix Do You Need?](https://aiweekender.substack.com/p/prompt-vs-rag-vs-fine-tuning-which) |
| love | paper | Hacker News | 70 | 58 | [LLMs Do More Than Next-Token Prediction: Beyond the Zeroth-Order Appro](https://gmcgoldr.github.io/2026/09/04/llm-next-token-predictors.html) |
| love | paper | Microsoft Research | 70 | 58 | [Memora: A Harmonic Memory Representation Balancing Abstraction and Spe](https://www.microsoft.com/en-us/research/blog/memora-a-harmonic-memory-representation-balancing-abstraction-and-specificity/) |
| love | announcement | TLDR AI | 68 | 62 | [OpenAI launches managed API for enterprise AI agent infrastructure](https://www.infoworld.com/article/4221163/openai-launches-managed-agents-api-to-simplify-enterprise-ai-agent-development.html) |
| love | model | TLDR AI | 66 | 60 | [Introducing MiniMax H3 Max: High-Quality Video Generation in Under 3 S](https://fal.ai/minimax-h3-max) |
| love | repo | Pointer | 60 | 75 | [Exo AI agent harness for recursive self-improvement](https://github.com/exoharness/exo) |
| love | rejected | The Generative Programmer | 58 | 42 | [8 Software Books AI Has Made More Relevant](https://generativeprogrammer.com/p/8-software-books-ai-has-made-more) |
| ok | blog | OpenAI Blog | 86 | 85 | [OpenAI's Real-Time Multimodal Voice Interaction System Architecture](https://openai.com/index/continuous-voice-interaction-with-gpt-live) |
| ok | blog | The Kaitchup – AI on a Budget | 85 | 62 | [Qwen3.8 27B Quantization: NVFP4, INT4, GSQ 3-bit, INT3/INT2, and Escha](https://kaitchup.substack.com/p/qwen38-27b-quantization-nvfp4-int4) |
| ok | model | Hugging Face Blog | 85 | 84 | [Training and Finetuning Multi-Vector Embedding Models with Sentence Tr](https://huggingface.co/blog/train-multi-vector-encoder) |
| ok | repo | AI News | 85 | 82 | [DeepSeek-V4-Flash GGUF Quantizations with Llama.cpp Checkpoint Fix (61](https://github.com/danielhanchen/llama.cpp/tree/deepseek-v4-checkpointing-fix) |
| ok | model | The Batch | 84 | 82 | [Gemini 3.5 Flash Model Card](https://deepmind.google/models/model-cards/gemini-3-5-flash/) |
| ok | paper | TLDR AI | 84 | 55 | [Verification-driven LLM Scaling Framework for Pre-training, Fine-tunin](https://llm-as-a-verifier.com/) |
| ok | repo | There's An AI For That | 84 | 75 | [VideoAgent: Graph-Powered Framework for Video Understanding, Editing,](https://github.com/HKUDS/VideoAgent) |
| ok | paper | MarkTechPost | 83 | 60 | [Microsoft's SkillOpt Shows Optimized Agent Skill Artifacts Transfer Ac](https://www.marktechpost.com/2026/08/05/microsoft-skillopt-agent-skill-transfer-portability/) |
| ok | model | TLDR AI | 80 | 82 | [North Small Translate: Multi-expert Model for 50+ Language Translation](https://cohere.com/blog/north-small-translate) |
| ok | product | Ben's Bites | 76 | 85 | [OpenAI Codex Plugins: Documentation for Extending AI with External Too](https://developers.openai.com/codex/plugins) |
| ok | repo | MarkTechPost | 75 | 60 | [Deploying Bonsai-27B 1-bit Models with PrismML and CUDA-Optimized llam](https://www.marktechpost.com/2026/07/28/deploying-a-1-bit-bonsai-27b-model-with-prismml-llama-cpp-and-openai-compatible-local-inference-workflows/) |
| ok | announcement | Simon Willison's Newsletter | 74 | 77 | [Kimi K3, and what we can still learn from the pelican benchmark](https://simonw.substack.com/p/kimi-k3-and-what-we-can-still-learn) |
| ok | model | Hugging Face Blog | 73 | 82 | [Ulysses Sequence Parallelism: Training with Million-Token Contexts](https://huggingface.co/blog/ulysses-sp) |
| ok | repo | There's An AI For That | 72 | 75 | [Meta releases AI4AnimationPy Python framework for motion-capture and r](https://github.com/facebookresearch/ai4animationpy) |
| ok | repo | MarkTechPost | 72 | 60 | [Supabase Releases Evals: an Open Source Benchmark That Scores Claude C](https://www.marktechpost.com/2026/08/01/supabase-releases-evals-an-open-source-benchmark-that-scores-claude-code-codex-and-opencode-on-real-supabase-tasks/) |
| ok | blog | The Rundown AI | 72 | 68 | [How to connect Higgsfield to Claude Code for multi-model image generat](https://app.therundown.ai/guides/turn-prompts-into-content-with-claude-code-higgsfield) |
| ok | paper | Microsoft Research | 72 | 84 | [SkillOpt: Agent skills as trainable parameters](https://www.microsoft.com/en-us/research/blog/skillopt-agent-skills-as-trainable-parameters/) |
| ok | blog | Simon Willison | 65 | 82 | [Generating running routes with GPT-6 Astra and ChatGPT Work](https://simonwillison.net/2026/Sep/12/astra-running-routes/) |
| ok | rejected | The AI Break | 62 | 66 | [Tutorial: Save $6K/year on Lead Scraping Platforms with AI](https://theaibreak.substack.com/p/tutorial-save-6kyear-on-lead-scraping) |
| ok | rejected | Machine Learning Pills | 58 | 45 | [Issue #135 - AI Agent Evals: What to Measure Beyond the Final Answer](https://mlpills.substack.com/p/issue-135-stop-testing-agents-like) |
| ok | rejected | aifeed.dev | 45 | 60 | [Denoisr - AI audio cleanup for podcasts and voice recordings](https://aifeed.dev/p/denoisr-ai-audio-cleanup-for-podcasts-and-voice-recordings) |
| ok | rejected | The Neuron | 45 | 45 | [Alibaba's 2.4T Qwen joins the AI race](https://www.theneurondaily.com/p/alibaba-s-2-4t-qwen-joins-the-ai-race) |
| noise | blog | MarkTechPost | 85 | 60 | [TileLang for High-Performance GPU Kernels: Tensor-Core GEMM, Fused Sof](https://www.marktechpost.com/2026/07/25/designing-high-performance-gpu-kernels-with-tilelang-tensor-core-gemm-fused-softmax-flashattention-and-autotuning/) |
| noise | blog | Hacker News | 84 | 45 | [Strix discovered Baseten production GitHub token with admin access](https://www.strix.ai/blog/baseten-harbor-github-pat-takeover) |
| noise | blog | AWS Machine Learning | 83 | 40 | [Build an AI-powered product tagging system with Amazon SageMaker serve](https://aws.amazon.com/blogs/machine-learning/build-an-ai-powered-product-tagging-system-with-amazon-sagemaker-serverless-model-customization/) |
| noise | repo | MarkTechPost | 82 | 60 | [Open Dreamer: JAX/Flax Implementation of Dreamer-4 World Model with Tr](https://www.marktechpost.com/2026/07/25/meet-open-dreamer-a-jax-flax-reproduction-of-the-dreamer-4-world-model-pipeline-with-the-full-training-recipe-published/) |
| noise | blog | Perplexity | 74 | 84 | [Optimizing Numerical Consistency in Apple Silicon On-Device Inference](https://www.perplexity.ai/hub/blog/optimizing-on-device-inference-for-apple-silicon) |
| noise | rejected | - | 74 | 72 | [GitHub - carloslfu/slotstream: Run Qwen3.8-Flash-Next (125B MoE, 104 G](https://github.com/carloslfu/slotstream) |
| noise | rejected | - | 73 | 84 | [Model Arena - Qwen3-ASR vs faster-whisper in real time](https://nanosamur.ai/blog/posts/qwen-vs-whisper/) |
| noise | blog | AWS Machine Learning | 73 | 40 | [Assessing PII Detection Performance Across Nine LLM-Based Detectors on](https://aws.amazon.com/blogs/machine-learning/model-agnostic-pii-detection-with-llms/) |
| noise | blog | The Rundown AI | 73 | 68 | [Automate a weekly marketing report using Claude Cowork skill-based wor](https://app.therundown.ai/guides/build-a-weekly-marketing-report-that-runs-itself-in-claude-cowork) |
| noise | rejected | Anthropic | 73 | 73 | [Formalizing Fermat's Last Theorem](https://www.anthropic.com/news/formalizing-fermats-last-theorem) |
| noise | rejected | Moonshot AI | 73 | 45 | [AI Docs Agent / Kimi Docs](https://www.kimi.com/it-it/features/docs) |
| noise | rejected | Moonshot AI | 73 | 45 | [Use Skills in Kimi Claw - Kimi Help Center](https://www.kimi.com/en/help/plugins-and-skills/use-skills-in-claw) |
| noise | blog | AWS Machine Learning | 72 | 40 | [AWS CloudFormation Template for Scalable Multi-Retrieval Enterprise Ag](https://aws.amazon.com/blogs/machine-learning/build-observable-enterprise-agentic-retrieval-using-managed-amazon-bedrock-knowledge-base-with-aws-cloudformation/) |
| noise | product | SAP News | 71 | 55 | [TabPFN-3.5 Plus Now Available in SAP AI Core for Instant Business Pred](https://news.sap.com/2026/09/tabpfn-35-plus-now-available-sap-ai-core-instant-business-predictions/) |
| noise | rejected | AI Disruption | 68 | 58 | [One Command to AI-Control Office](https://aidisruption.ai/p/one-command-to-ai-control-office) |
| noise | repo | Hacker News | 66 | 73 | [ClawRun hosts open-source AI agents on Vercel and manages lifecycle](https://github.com/clawrun-sh/clawrun) |
| noise | rejected | Together AI | 60 | 60 | [The Open Source AI Stack](https://www.together.ai/blog/the-open-source-ai-stack) |
| noise | rejected | The AI Maker | 58 | 38 | [Monthly Q&A #5: Building Sites, Researching LinkedIn, and Filtering Ne](https://aimaker.substack.com/p/ai-workflows-research-resumes-content) |
| noise | rejected | Loop Engineering | 55 | 42 | [How to Turn Claude Fable 5 Into a High-Performance Consulting Agent](https://linas.substack.com/p/claude-fable-5-mckinsey-consulting-engine) |
| noise | rejected | Replit | 45 | 45 | [Agent Dashboard: Track Performance with AI / Replit](https://replit.com/build/agent-dashboard) |
| noise | rejected | aifeed.dev | 45 | 60 | [Vynaris — AI inference that shows its receipts](https://aifeed.dev/p/vynaris-ai-inference-that-shows-its-receipts) |

## What the old scorer got wrong

Scored by the deployed rubric, single run: noise kept 11 of 21, loved dropped 13
of 27, mean score 65.7 for loved against 65.6 for noise — wrong in both
directions, with no separating power at all.

Consistently scored high but unwanted: cloud vendor how-tos using their own
product (3 AWS items, one SAP availability notice), an aggregator's tutorial or
reimplementation (MarkTechPost: 0 loves in 5), product docs and help centres and
dashboards, vendor micro-optimisation posts nobody asked for.

Consistently scored low but wanted: runnable tools (Exo 60, BrowserSkill 73,
PyScrappy 82), practitioner write-ups with numbers (the context tax 73, ML Pills
73, Rig 82), papers explaining a mechanism (next-token 70, Memora 70), and model
launches reported by a newsletter (MiniMax H3 66, Moonshot 72) while the same
class of launch from The Batch got 96.

## 20 more, all confirmed wanted

Picked from feed history as a check on the profile rather than a scored sample.
Every one of these should be approved.

- **tools:** TurboPrefill (llama.cpp PR), Needle (Gemini tool-calling in 26M),
  MenteDB, a spec-driven-development skill, open-r1, DeepClaude
- **practitioner:** Spotify cutting Claude Code tokens 90%, kapa.ai pruning RAG
  context 68%, JetBrains on agent evaluation, the DeepSeek-V3 performance
  analysis, Anthropic's code migrations, reading the Claude Code source
- **papers:** layer duplication, one-layer RL, hidden-state probes, FairyFuse,
  Tokenomics
- **releases:** DeepSeek-V4-Flash, Kimi K2.7-Code
- **individual:** the Ralph coding agent (AI Hero)

The profile, in one line: someone else's working code, a number with a method
behind it, or weights you can pull.

## Coverage cases

Added 2026-09-23 with the collector/judge split (ADR 11). The pipeline no
longer drops a second outlet's copy of a story, so the agent sees every copy and
has to pick one. Each case is one story several publishers carried; the label
says which item is approved and which are rejected as retellings.

To build a case: restore the newest dump (`scripts/restore-db.sh`), find a story
three or more publishers carried in one week — `duplicate` rejects with the same
`detail->>'dup_of'`, or articles whose embeddings sit under 0.30 of each other —
and write down every copy with the verdict it should get.

| case | story | item | publisher | label |
|---|---|---|---|---|
| 1 | GPT-6 Astra release | *to fill from the dump* | | |
| 2-5 | multi-copy stories | *to fill from the dump* | | |

Each case lands right when the approved item is the labelled one (the
first-party post where one was queued) and every other copy is rejected with a
reason that names the retelling.

## Runs

| date | rubric | noise kept | loved dropped | coverage cases | notes |
|---|---|---|---|---|---|
| 2026-09-23 | collector/judge split | not run | not run | not run | The cases above are not filled yet, and the session that wrote the rubric change could not reach the articles (network policy). Run before the schedule picks this rubric up. |
