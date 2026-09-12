// The summary shown under an article's title. Called by
// pipeline/steps/summarize.py before insert (an article it cannot summarize is
// not inserted), and by scripts/summarize_articles.py to backfill older rows.
//
// Nemotron directly, no Nvidia fallback: a summary that silently came from
// Ministral would be written in a different voice. A NIM outage holds the
// run's articles for the next run instead.
//
// Its own client, not the shared `Nemotron` in clients.baml: that one carries
// `timeout 120` in options, which integrate.api.nvidia.com rejects as an
// unsupported body param (400). Infomaniak ignores it, so `Ministral` and the
// `Nvidia` fallback never tripped over it.
client<llm> NemotronSummary {
  provider openai-generic
  retry_policy Burst
  options {
    base_url "https://integrate.api.nvidia.com/v1"
    api_key env.NVIDIA_NIM_API_KEY
    model "nvidia/nemotron-3-super-120b-a12b"
  }
}

function SummarizeArticle(title: string, content: string, bullet_count: int) -> string {
  client NemotronSummary
  prompt #"
    {{ _.role("system") }}
    You write short article summaries in the voice of Julia Evans (jvns.ca):
    warm, curious, plain-spoken, concrete.

    Voice rules:
    - Short sentences. Everyday words. Contractions are fine.
    - Explain any jargon in a few words the first time it appears.
    - Enthusiastic but grounded - "this is a neat idea" is fine, "game-changing" is not.
    - Say what a reader actually learns or can do.
    - No marketing language, no hype, no rhetorical build-up, no closing pep talk.
    - Do NOT invent first-person experience ("I tried this and...") or any fact
      the article does not state. Summarize only what is there.
    - Write in English only.

    {{ _.role("user") }}
    Summarize the article below as a hook line followed by bullets.

    Format, exactly:
    - Line 1: the hook - one plain sentence saying what this is and why a
      developer would care. No label, no bullet character.
    - Then {{ bullet_count }} lines, each starting with "- ", one concrete
      detail each: how it works, numbers, requirements, what's new. Terse,
      not full sentences where a fragment does.
    - If the article states a real limitation or open question, add one final
      line starting with "- Catch: ".

    No blank lines. No headers. No numbering. No markdown bold or backticks.

    Title: {{ title }}

    Content:
    {{ content }}

    {{ ctx.output_format }}
  "#
}

// ─── Tests ──────────────────────────────────────────────────────────────────
// Format asserts mirror the prompt: a hook line, then exactly `bullet_count`
// bullets, then an optional "- Catch:" line, no blank lines.
//
// Line checks use `lines` and `regex_match`, never a "\n" string: inside an
// assert "\n" stays a literal backslash-n, so `"\n" in this` is always false
// and `split("\n")` never splits. regex_match reads the same \n as a newline.
//
// The CJK cases matter most. pipeline/steps/summarize.py rejects a summary
// with a single CJK (or Cyrillic, Arabic, Hebrew) character anywhere, and a
// rejected summary means the article is not inserted.
//
// Run: cd backend && uv run --env-file ../.env baml-cli test --from baml_src -i "SummarizeArticle::"

test summarize_stated_limitation_gets_a_catch {
  functions [SummarizeArticle]
  args {
    bullet_count 3
    title "A tiny CLI for tailing Postgres logs"
    content #"
      pgtail is a small command-line tool that follows a Postgres server's log
      file and colourises slow queries. It reads the `log_min_duration_statement`
      setting to decide what counts as slow. It has no dependencies beyond libpq
      and is a single Go binary. The author notes it does not yet handle log
      rotation, so a rotated file stops being followed until you restart it.
    "#
  }
  @@assert(hook_first, {{ this[:2] != "- " }})
  @@assert(no_blank_lines, {{ not (this|trim|regex_match("(?s).*\n\s*\n.*")) }})
  @@assert(hook_bullets_catch, {{ this|trim|lines|list|length == 5 }})
  @@assert(has_catch, {{ "- Catch:" in this }})
}

test summarize_no_limitation_no_catch {
  functions [SummarizeArticle]
  args {
    bullet_count 4
    title "uv 0.9 adds an outdated-dependency view"
    content #"
      uv 0.9 ships `uv tree --outdated`, which prints the dependency tree with
      the latest available version next to each package that is behind. It
      reads the lockfile, so it needs no network call for the tree itself, only
      for the version lookup. The release also makes `uv sync` about 20% faster
      on large workspaces by caching resolved markers between runs, and adds
      `uv python pin --global` to set a default interpreter for every project.
      Windows users get native ARM64 builds. Upgrading is `uv self update`.
    "#
  }
  @@assert(hook_first, {{ this[:2] != "- " }})
  @@assert(no_blank_lines, {{ not (this|trim|regex_match("(?s).*\n\s*\n.*")) }})
  @@assert(hook_and_4_bullets, {{ this|trim|lines|list|length == 5 }})
  @@assert(no_invented_catch, {{ "Catch:" not in this }})
}

test summarize_six_bullets_for_a_long_article {
  functions [SummarizeArticle]
  args {
    bullet_count 6
    title "Serving a 70B model on two consumer GPUs"
    content #"
      This post walks through serving a 70-billion-parameter model on two RTX
      4090 cards (24GB each) for a small internal team. The model is quantized
      to 4-bit with AWQ, which brings the weights to about 38GB, so they are
      split across both cards with tensor parallelism in vLLM.

      Throughput settles at 28 tokens per second for a single user and 190
      tokens per second aggregate at 16 concurrent requests. The KV cache is the
      real limit: with 4-bit weights there is room for roughly 12K tokens of
      context per request at that concurrency. The author sets
      `--max-model-len 16384` and lets vLLM's paged attention handle the rest.

      Power draw peaks at 820W for the whole box, so the author capped each card
      at 300W with `nvidia-smi -pl 300`, which cost about 8% throughput and
      dropped temperatures by 12 degrees.

      Quality was checked on the team's own 200-question eval: the 4-bit model
      scored 81% against 84% for the fp16 version run on a rented H100. The
      author considers that close enough for code review and drafting.

      The full setup, including the systemd unit and the Caddy reverse proxy
      config, is in the linked repo. Total hardware cost was about $3,600.
      The one open problem is cold start: loading the weights takes 4 minutes,
      so the service is never scaled to zero.
    "#
  }
  @@assert(hook_first, {{ this[:2] != "- " }})
  @@assert(no_blank_lines, {{ not (this|trim|regex_match("(?s).*\n\s*\n.*")) }})
  @@assert(hook_6_bullets_maybe_catch, {{ this|trim|lines|list|length in [7, 8] }})
}

test summarize_chinese_article_in_english {
  functions [SummarizeArticle]
  args {
    bullet_count 3
    title "Qwen3-Coder-Mini 发布"
    content #"
      Qwen 团队发布了 Qwen3-Coder-Mini，一个 70 亿参数的开源代码模型。它支持
      128K 上下文，在单张 24GB 显卡上即可运行。模型采用 Apache 2.0 许可证，
      权重已上传到 Hugging Face。团队表示，它在 HumanEval 上得分 82%，但在长文件
      重构任务上仍落后于更大的模型。
    "#
  }
  @@assert(no_cjk, {{ "团队" not in this and "模型" not in this and "开源" not in this and "上下文" not in this and "显卡" not in this and "发布" not in this }})
  @@assert(hook_first, {{ this[:2] != "- " }})
  @@assert(no_blank_lines, {{ not (this|trim|regex_match("(?s).*\n\s*\n.*")) }})
}

test summarize_does_not_copy_a_native_name {
  functions [SummarizeArticle]
  args {
    bullet_count 3
    title "Alibaba ships a Qwen3.8 preview"
    content #"
      Alibaba's Tongyi Qianwen team (通义千问) released a preview of Qwen3.8,
      an open-weight model with a 1M-token context window. The team says the
      preview is updated daily during the preview period; its announcement post
      was titled "持续变强" ("getting stronger every day"). Weights are on
      Hugging Face under the Qwen license. Reported gains are largest on web
      frontend generation, where it scores 71% on the team's own WebDev bench,
      up from 58% for Qwen3.5. No third-party evaluations exist yet.
    "#
  }
  @@assert(no_cjk, {{ "通义千问" not in this and "持续变强" not in this and "通义" not in this }})
  @@assert(hook_first, {{ this[:2] != "- " }})
  @@assert(no_blank_lines, {{ not (this|trim|regex_match("(?s).*\n\s*\n.*")) }})
}

test summarize_strips_markdown_from_the_source {
  functions [SummarizeArticle]
  args {
    bullet_count 3
    title "Why we moved our job queue off Redis"
    content #"
      ## Why we moved off Redis

      **TL;DR:** we replaced our Redis job queue with Postgres and `SKIP LOCKED`.

      ### The problem

      Redis was a second stateful service to back up and monitor, and a
      failover once lost about 400 queued jobs. Our peak load is **2,000 jobs
      per minute**, well within what Postgres handles.

      ### The fix

      ```sql
      SELECT id FROM jobs WHERE state = 'queued'
      ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 10;
      ```

      Workers poll every 500ms. Jobs now commit in the same transaction as the
      data they touch, so a job can never run against a row that was rolled
      back. p99 pickup latency went from 40ms to 180ms, which we accepted.
    "#
  }
  @@assert(no_bold, {{ "**" not in this }})
  @@assert(no_backticks, {{ "`" not in this }})
  @@assert(no_headers, {{ "##" not in this }})
  @@assert(hook_first, {{ this[:2] != "- " }})
  @@assert(no_blank_lines, {{ not (this|trim|regex_match("(?s).*\n\s*\n.*")) }})
}

test summarize_drops_the_hype {
  functions [SummarizeArticle]
  args {
    bullet_count 3
    title "Introducing FlowForge AI"
    content #"
      Introducing FlowForge AI - the revolutionary, game-changing platform that
      will transform how your team builds agents forever! Unleash the power of
      AI today.

      FlowForge lets you chain LLM calls in a visual editor and export the
      result as a plain Python script. It supports OpenAI and Anthropic models
      out of the box, with retries and a per-step cost readout. The free tier
      includes 1,000 runs per month; the paid plan is $29 per month per seat.
      Self-hosting is not available yet.
    "#
  }
  @@assert(no_hype, {{ "revolutionary" not in this|lower and "game-changing" not in this|lower and "unleash" not in this|lower }})
  @@assert(hook_first, {{ this[:2] != "- " }})
  @@assert(no_blank_lines, {{ not (this|trim|regex_match("(?s).*\n\s*\n.*")) }})
}
