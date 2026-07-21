---
title: "Why I moved agentique's LLM layer to BAML"
description: "Structured output, prompt tests in VSCode, and provider fallbacks: how BAML replaced ad-hoc LLM code in agentique's news pipeline."
slug: why-i-moved-agentiques-llm-layer-to-baml
topic: prompt-engineering
date: 2026-07-21
articles:
  - https://docs.boundaryml.com/home
  - https://boundaryml.com/blog/schema-aligned-parsing
  - https://github.com/BoundaryML/baml
---

When I started building https://agentique.ch, I thought the only hard part would be
ranking AI articles. It turned out there was another problem — keeping the
LLM layer maintainable while constantly experimenting with different models
and providers.

## A bit of context

Agentique is an AI news aggregator for developers. The goal isn't to cover
*all* AI news — funding rounds, acquisitions, or how large AI labs cope with
government affairs is out of scope. I'm much more interested in individual
contributors or small teams sharing insights: blog posts about agent
orchestration systems, GitHub repos solving a problem I ran into the week
before, dev workflows that made an assistant twice as useful.

To surface that, agentique collects articles from a curated list of
technical sources and runs them through a pipeline: fetch, deduplicate, score
relevance, improve titles, generate summaries, publish. Most stages involve
one or more LLM calls, which means every stage has prompts, schemas, model
selection, retries, and tests. After a while the LLM layer became its own 
subsystem. That's when I started looking for better tooling.

## Looking at the alternatives

Before settling on [BAML](https://docs.boundaryml.com/home), I compared the
existing ecosystem. Vercel AI SDK is excellent for building AI directly into
a web app — streaming, React integration, provider abstraction. Mastra looks
great for long-running agents, workflows, memory, RAG. LangChain/LangGraph is
still the most complete orchestration framework for complex agent systems.

My problem was different — I wasn't building autonomous agents or
conversational UIs. I needed a reliable, well-organized way of expressing
dozens of independent LLM tasks: classify article, improve title, generate
summary, extract metadata, score relevance. Each one should look like a
normal function in the codebase — typed inputs, typed outputs, easy testing,
easy model switching, minimal boilerplate. That's the niche BAML fills: a DSL
for turning prompts into typed functions with reliable structured output.

## What I liked most

**Prompt tests.** Every prompt lives together with its tests, right in the
same `.baml` file, and the BAML VSCode extension runs them like unit tests
from the editor. When I switch from Gemini to GPT-OSS, or tweak a prompt, I
immediately know whether I've broken something. That removes a surprising
amount of uncertainty.


## Prompt tests

Every prompt lives together with its tests.

Here's a simplified example from my title rewriting pipeline.

```baml
function ImproveTitles(articles: ArticleInput[]) -> TitleFix[] {
  client GeneralClient
  prompt #"
    {{ _.role("system") }}
    You are a technical editor. You write clear, informative article titles.

    Output rules (strict):
    - For each input article, return one TitleFix whose `url` exactly matches that article's URL.
    - The `title` field contains plain title text ONLY. No markdown - strip ** or * or _ or backticks.
    - Write in English. Never emit any other language or script.

    {{ _.role("user") }}
    Decide for each article whether the existing title is already good. A good title is specific, informative ... 
    - If the existing title is already good, return it verbatim.
   
    {% for a in articles %}
    --- Article {{ loop.index }} ---
    url: {{ a.url }}
    current_title: {{ a.title }}
    snippet: {{ a.snippet }}
    {% endfor %}

    {{ ctx.output_format }}
  "#
}
```

And here's the test: 

```baml
test improve_titles_rewrite_short {
  functions [ImproveTitles]
  args {
    articles [
      {
        url "https://example.com/claude"
        title "Claude 4"
        snippet "Anthropic today released Claude 4, a new flagship model with improved reasoning and a 1M-token context window."
      }
    ]
  }
}

test improve_titles_keep_unchanged {
  functions [ImproveTitles]

  args {
    articles [
      {
        url "https://example.com/post"
        title "Anthropic releases Claude 4 with 1M-token context window"
      }
    ]
  }
}

@@assert(no_markdown, {{ "**" not in this[0].title }})
@@assert(no_cjk, {{ "伊" not in this[0].title }})
@@assert(max_12_words, {{ this[0].title|split(" ")|list|length <= 12 }})
```

**Structured output, done as parsing, not retrying.** 
Every prompt returns a typed object. No JSON parsing.

No "please output valid JSON."

No markdown cleanup.

No repairing malformed responses.

**Provider fallbacks that live in the DSL, not my code.** 
Routing between providers is declared once, not scattered across application logic:

```baml
client<llm> GeneralClient {
  provider fallback
  options {
    strategy [GeminiFlash, NvidiaGptOss, NvidiaMinistral]
  }
}
```

If Gemini is unavailable, the next provider in the strategy is tried
automatically. The application code still just calls `ImproveTitles(...)` —
it stays unaware of which provider ultimately serves the request.

## The funny part

One of the goals of Agentique was to help me discover technical content I
probably wouldn't have found otherwise. BAML ended up being one of those
discoveries — I found the [project on GitHub](https://github.com/BoundaryML/baml),
added it to the feed because it looked interesting, gave it a try a few days
later, and it ended up replacing my entire LLM layer.
