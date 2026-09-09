import { useQueries } from "@tanstack/react-query"

import { type ArticlePublic, ArticlesService } from "@/client"
import { BOX_LIMIT, BOX_SORT, BOX_WINDOW_DAYS, type TopicDef } from "./topics"

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

/**
 * Start of the window, snapped to midnight UTC. Snapping matters: the value
 * goes into the query key, so a raw `now - 14d` would mint a new key on every
 * render and refetch every box forever.
 */
function windowStart(): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() - BOX_WINDOW_DAYS)
  d.setUTCHours(0, 0, 0, 0)
  return d.toISOString()
}

// Must match BOX_SORT: the merge only recovers a box's true top-10 if the
// client orders the union the same way the API ordered each part.
function scoreDesc(a: ArticlePublic, b: ArticlePublic): number {
  return b.score - a.score || b.id - a.id
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
  const since = windowStart()

  return useQueries({
    queries: expandTopic(def).map((part) => ({
      // Keyed by the request, not by the box, so boxes sharing a tag share a
      // fetch — `quantization` appears in both make-it-fast and small-models,
      // and react-query dedupes identical keys for free.
      queryKey: [
        "articles",
        { ...part, limit: BOX_LIMIT, sort: BOX_SORT, since },
      ],
      queryFn: () =>
        ArticlesService.readArticles({
          ...part,
          limit: BOX_LIMIT,
          sort: BOX_SORT,
          since,
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
        articles: [...byId.values()].sort(scoreDesc).slice(0, BOX_LIMIT),
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
