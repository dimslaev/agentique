---
title: "The RAG problem nobody likes to admit"
description: "A 0.6B model doing 100k searches a second at LinkedIn, and why throwing away 68% of your retrieved context is the fix."
slug: whats-new-in-rag
topic: rag
date: 2026-07-13
articles:
  - https://machinelearningatscale.substack.com/p/linkedin-architecture-for-production
  - https://www.kapa.ai/blog/how-we-prune-rag-context
  - https://blitzgraph.com
  - https://machinelearningatscale.substack.com/p/analysis-of-splare-sparse-autoencoders
  - https://blog.bytebytego.com/p/ep220-rag-vs-graph-rag-vs-agentic
  - https://machinelearningatscale.substack.com/p/the-32400-search-model-that-silently
---

I've noticed a pattern in the RAG writing I read this week: nobody's excited
about finding relevant chunks anymore. The interesting part is throwing most
of them away.

Take LinkedIn's [production search architecture](https://machinelearningatscale.substack.com/p/linkedin-architecture-for-production).
The ranker is a 0.6-billion-parameter model, and it handles over 100,000
queries a second. Not because a bigger model would be worse — it's that at
that volume, small and fast wins by a mile. I think about that number every
time someone tells me they need a bigger embedding model before they've
actually tried a smaller one.

Kapa.ai's [write-up on pruning RAG context](https://www.kapa.ai/blog/how-we-prune-rag-context)
is the same idea from a different angle. They put a small model between the
retriever and the generator, and it drops 68% of the retrieved text while
keeping 96% of the useful answer. If you're paying to stuff twenty chunks
into a prompt so the model can actually use three of them, this is worth
copying — it's a genuinely simple thing to bolt on.

Two pieces this week made me rethink what "retrieval" even means.
[BlitzGraph](https://blitzgraph.com) bills itself as "Supabase for graphs" —
retrieval by relationship instead of similarity, for the cases where "these
two things are connected" matters more than "these two things sound alike."
And ByteByteGo's [comparison of RAG, Graph RAG, and Agentic RAG](https://blog.bytebytego.com/p/ep220-rag-vs-graph-rag-vs-agentic)
is the clearest explanation I've seen of why those three aren't
interchangeable — pick the wrong one and you're rebuilding in six months.

On the research end, an [analysis of SPLARE](https://machinelearningatscale.substack.com/p/analysis-of-splare-sparse-autoencoders)
swaps out the usual embedding approach for sparse autoencoders and beats
SPLADE on the MMTEB benchmarks. Early, but a sign dense embeddings aren't
the only game in town anymore.

The one I keep thinking about, though, is the [story of a search model that
quietly started ranking the CEO's memos above everything else](https://machinelearningatscale.substack.com/p/the-32400-search-model-that-silently).
No error, no warning — it just returned the wrong thing, confidently, until
someone happened to notice. That's the real risk in RAG. It doesn't crash.
It just quietly gets worse.

If I only did one thing from this list, it'd be pruning context before
generation. A 68% smaller prompt with 96% of the recall beats swapping
embedding models, and you can ship it this week.
