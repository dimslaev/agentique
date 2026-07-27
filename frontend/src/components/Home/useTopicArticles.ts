import { useQueries } from "@tanstack/react-query"

import { type ArticlePublic, ArticlesService } from "@/client"
import { BOX_LIMIT, BOX_SORT, type TopicDef } from "./topics"

type QueryPart = {
  tag?: string
  kind?: string
  category?: string
}

/**
 * One request per tag x kind pair. A box with neither (never happens today,
 * but the shape allows it) collapses to a single unfiltered request.
 */
export function expandTopic(def: TopicDef): QueryPart[] {
  const tags = def.tags?.length ? def.tags : [undefined]
  const kinds = def.kinds?.length ? def.kinds : [undefined]

  const parts: QueryPart[] = []
  for (const tag of tags) {
    for (const kind of kinds) {
      parts.push({ tag, kind, category: def.category })
    }
  }
  return parts
}

function publishedDesc(a: ArticlePublic, b: ArticlePublic): number {
  // `published_at` is nullable in the schema (zero nulls in practice) —
  // sort any that appear to the bottom rather than to 1970.
  const left = a.published_at
    ? Date.parse(a.published_at)
    : Number.NEGATIVE_INFINITY
  const right = b.published_at
    ? Date.parse(b.published_at)
    : Number.NEGATIVE_INFINITY
  return right - left || b.id - a.id
}

export type TopicArticles = {
  articles: ArticlePublic[]
  isPending: boolean
  isError: boolean
}

/**
 * Fetches and merges the parts of one box. Pass `enabled: false` until the box
 * is near the viewport — see `useInView`.
 */
export function useTopicArticles(
  def: TopicDef,
  enabled: boolean,
): TopicArticles {
  return useQueries({
    queries: expandTopic(def).map((part) => ({
      // Keyed by the request, not by the box, so boxes sharing a tag share a
      // fetch — `quantization` appears in both make-it-fast and small-models,
      // and react-query dedupes identical keys for free.
      queryKey: ["articles", { ...part, limit: BOX_LIMIT, sort: BOX_SORT }],
      queryFn: () =>
        ArticlesService.readArticles({
          ...part,
          limit: BOX_LIMIT,
          sort: BOX_SORT,
        }),
      enabled,
      staleTime: 5 * 60 * 1000,
    })),
    combine: (results) => {
      const byId = new Map<number, ArticlePublic>()
      for (const result of results) {
        for (const article of result.data?.data ?? []) {
          if (!byId.has(article.id)) byId.set(article.id, article)
        }
      }

      return {
        articles: [...byId.values()].sort(publishedDesc).slice(0, BOX_LIMIT),
        // A disabled query reports `pending`, which is what we want: a box
        // that has not scrolled into view yet should render as loading.
        isPending: results.some((result) => result.isPending),
        // Partial failures still render what came back; only a total failure
        // is worth showing an error for.
        isError:
          results.length > 0 && results.every((result) => result.isError),
      }
    },
  })
}
