import { useQuery } from "@tanstack/react-query"

import { type ArticlePublic, ArticlesService } from "@/client"
import { BOX_LIMIT, BOX_SORT, type TopicDef } from "./topics"

export type TopicArticles = {
  articles: ArticlePublic[]
  isPending: boolean
  isError: boolean
}

/**
 * One lane, one request.
 *
 * This used to fan out into a request per tag x kind pair and merge the results
 * client-side, with a correctness argument attached about why merging top-10s
 * by date recovered the true top-10. None of that is needed now that a lane is
 * a single `category` filter the server answers directly — the merge, the
 * dedupe, and the argument all went with it.
 *
 * Pass `enabled: false` until the lane is near the viewport — see `useInView`.
 */
export function useTopicArticles(
  def: TopicDef,
  enabled: boolean,
): TopicArticles {
  const query = useQuery({
    queryKey: [
      "articles",
      { category: def.slug, limit: BOX_LIMIT, sort: BOX_SORT },
    ],
    queryFn: () =>
      ArticlesService.readArticles({
        category: def.slug,
        limit: BOX_LIMIT,
        sort: BOX_SORT,
      }),
    enabled,
    staleTime: 5 * 60 * 1000,
  })

  return {
    articles: query.data?.data ?? [],
    // A disabled query reports `pending`, which is what we want: a lane that
    // has not scrolled into view yet should render as loading.
    isPending: query.isPending,
    isError: query.isError,
  }
}
