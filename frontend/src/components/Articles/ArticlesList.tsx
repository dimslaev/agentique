import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ArticlesService } from "@/client"
import { useFilters } from "@/context/filters"
import { cn } from "@/lib/utils"
import { ArticleRow } from "./ArticleRow"
import { SCORE_STANDOUT } from "./ScoreRail"

const PUBLISHED_DAYS: Record<string, number> = { "3d": 3, "1w": 7, "1m": 30 }

function cutoffIso(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString()
}

export function ArticlesList() {
  const { filters } = useFilters()
  const { search, dateRange, sort, category, kind, publisher, tag } = filters

  const since = cutoffIso(PUBLISHED_DAYS[dateRange] ?? 7)

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: [
      "articles",
      search,
      dateRange,
      sort,
      category,
      kind,
      publisher,
      tag,
    ],
    queryFn: () =>
      ArticlesService.readArticles({
        limit: 50,
        since,
        q: search || undefined,
        sort,
        category: category || undefined,
        kind: kind || undefined,
        publisher: publisher || undefined,
        tag: tag || undefined,
      }),
    placeholderData: keepPreviousData,
  })

  if (isLoading) {
    return null
  }

  if (isError || !data) {
    return (
      <div className="py-12 text-sm text-destructive">
        Failed to load articles.
      </div>
    )
  }

  const articles = data.data

  return (
    <div className="relative">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-border pb-3">
        <h1 className="font-display text-sm font-bold uppercase tracking-[0.1em]">
          The wire
        </h1>
        <div className="flex items-center gap-5 font-wire text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          <span className="flex items-center gap-2">
            <span className="inline-block h-3 w-0.5 shrink-0 bg-primary" />
            scores {SCORE_STANDOUT}+
          </span>
          <span className="flex items-center gap-2">
            <span className="inline-block h-3 w-0.5 shrink-0 bg-foreground/40" />
            bar height = score
          </span>
        </div>
      </div>

      {articles.length === 0 ? (
        <div
          data-testid="articles-empty"
          className="py-12 text-sm text-muted-foreground"
        >
          No articles found.
        </div>
      ) : (
        <ul
          data-testid="articles-list"
          className={cn(
            "transition-opacity duration-200",
            isFetching && "opacity-50",
          )}
        >
          {articles.map((article) => (
            <ArticleRow key={article.id} article={article} />
          ))}
        </ul>
      )}

      {!isFetching && articles.length > 0 && (
        <p className="pt-4 font-wire text-xs text-muted-foreground">
          {articles.length} article{articles.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  )
}
