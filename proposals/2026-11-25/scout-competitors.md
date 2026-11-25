# scout-competitors 2026-11-25

- Ahead: https://huggingface.co/blog/harness-adapters-at-scale +79h (AINews). That is our only lead among dated stories. Their dates are day-only, so I set them to 12:00 UTC.
- Behind on 12 of 13 dated matches (AINews 5, AI/TLDR 7). The largest gaps are https://github.com/sous-labs/songe -113h and https://huggingface.co/nari-labs/Qwen3.8-27B-NariQ-GGUF -89h (AI/TLDR). The other 10 are -17h: they post the same day, and we publish once a day at about 05:00 UTC the next morning. We rejected 8 of their stories. The most common reason was "AI for science/maths out of scope" (4: OpenAI VP≠VNP, GPT-6 protein design, Astra exoplanets, DeepMind quantum algorithms). One reject looks wrong: https://claude.com/resources/articles/install-as-app was rejected as a consumer feature, but it turns artifacts into installable apps with connectors, which is a surface builders ship on. Wrong rejects: 1.
- Never reached us: AINews 2 of 16, AI/TLDR 13 of 23, Aligned News unknown (feed unreadable). The most common cause is the AI/TLDR mail source. It has produced 1 scored_url row ever (2026-10-24) and 0 articles, so any story only AI/TLDR carries is lost. Of those 13: 4 are changelogs we poll nowhere (VS Code 1.148, Claude Code 2.1.332, Codex CLI 0.172.0, OpenCode 2.4.0), and 2 came out on Nov 25 after our last run (Anthropic's Messages API move to Rust, Google's Cogentic papers). The AINews misses (Enterprise Frontier Safeguards ZDR beta, GPT-6 Cyber's 948 Linux kernel bugs) are links in the Nov 23-24 issues that never became candidates. Our runs score the issue itself and reject it as a digest. Never reached in total: 15.
- Errors: the Latent Space feed (`latent.space/feeds/news.xml`, also tried with `www.`) and the Aligned News RSS (`alignednews.com/feed.xml`) failed twice each in web_fetch ("No readable content"). curl was refused by the proxy (403). I rebuilt the AINews list from 5 issue pages (Nov 18, 20, 21, 23, 24) found by web_search. I could not read Aligned News at all, so it has no story list. Our DB shows its feed has delivered nothing since 2026-11-21 04:00 UTC: 4 nightly runs, 0 candidates.
- Features: `tool-timelines` (AI/TLDR): a page per product (Claude Code, Codex CLI, OpenCode, Antigravity) listing every article about it, newest first. Our tags stop at vendor level. Readers use it to catch up on the one tool they run. `daily-email-option` (AINews): readers pick a daily email of the night's approved articles as well as the weekly issue. AINews lets subscribers choose how often they get email. Readers who want news the same day get it without checking the site. Aligned News: none, site unreadable.

Ledger:
- tool-timelines | One page per product listing every article about it, newest first | proposed
- daily-email-option | Let readers choose a daily email of approved articles as well as the weekly issue | proposed

## Details

Never reached (AI/TLDR unless marked):
- https://www.anthropic.com/research/migrating-api-to-rust (Nov 25, after run)
- Google Cogentic math papers (Nov 25, after run)
- https://code.visualstudio.com/updates/v1_148 (changelog)
- Claude Code 2.1.332 (Nov 25 01:49 UTC, changelog)
- Codex CLI 0.172.0 (Nov 24, changelog)
- OpenCode 2.4.0 (Nov 23, changelog)
- https://prismml.com/news/prismml-launches-ternary-bonsai-2-5-27b (Nov 24)
- https://claude.com/resources/articles/zero-data-retention-with-enterprise-frontier-safeguards (Nov 23, AINews too)
- Anthropic VP≠VNP repo (Nov 23). We saw only OpenAI's version and rejected it.
- OpenAI matrix multiplication exponent 9/4 preprint (Nov 24)
- LessWrong side channels through a shared vLLM server, Deshpande and Africa (Nov 19)
- DeepMind Mass Spec Skills for Antigravity (undated)
- LlamaIndex OCRia-nano-1 (undated). We carried OCRia-1.5 on Nov 20.
- GPT-6 Cyber Linux kernel research post, Nov 23 (AINews). We only have the Nov 6 GPT-6 Cyber launch post.

Rejected, with stage below_threshold:
- METR Q4 capability update: removed by hand
- Jensen reinstated: corporate
- OpenAI "Perplexity and Intelligence": policy. We saw it Nov 23 04:00, before AINews ran it.
- OpenAI VP≠VNP: maths
- GPT-6 protein design: bio
- Astra exoplanets: science
- Install as App: consumer
- DeepMind quantum algorithms: science
