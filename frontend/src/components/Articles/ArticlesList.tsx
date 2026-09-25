import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ArticlesService } from "@/client"
import { useFilters } from "@/context/filters"
import { cn } from "@/lib/utils"
import { ArticleRow } from "./ArticleRow"
import { FilterOptions } from "./FilterOption"
import { SCORE_STANDOUT } from "./ScoreRail"

const PUBLISHED_DAYS: Record<string, number> = { "3d": 3, "1w": 7, "1m": 30 }

const DATE_OPTIONS = [
  { value: "3d", label: "3 days" },
  { value: "1w", label: "Week" },
  { value: "1m", label: "Month" },
]

const SORT_OPTIONS = [
  { value: "published_at-desc", label: "Date" },
  { value: "score-desc", label: "Score" },
  { value: "likes-desc", label: "Popular" },
]

function cutoffIso(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString()
}

export function ArticlesList() {
  const { filters, setFilter, setTag } = useFilters()
  const { search, dateRange, sort, category, kind, tag } = filters

  const since = cutoffIso(PUBLISHED_DAYS[dateRange] ?? 7)

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ["articles", search, dateRange, sort, category, kind, tag],
    queryFn: () =>
      ArticlesService.readArticles({
        limit: 50,
        since,
        q: search || undefined,
        sort,
        category: category || undefined,
        kind: kind || undefined,
        tag: tag || undefined,
      }),
    placeholderData: keepPreviousData,
  })

  const articles = data?.data ?? []

  return (
    <div className="relative">
      {/* Published and Sort change how the wire is shown rather than what is
          on it, so they sit with the wire instead of with the filters. */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 border-b pt-5 pb-3">
        <h1 className="font-display text-sm font-bold uppercase tracking-[0.1em] max-sm:w-full">
          The wire
        </h1>
        <div className="flex flex-wrap gap-x-5 max-sm:-ml-2">
          <FilterOptions
            label="Published"
            options={DATE_OPTIONS}
            value={dateRange}
            onChange={(v) => setFilter("dateRange", v)}
          />
          <FilterOptions
            label="Sort by"
            options={SORT_OPTIONS}
            value={sort}
            onChange={(v) => setFilter("sort", v)}
          />
        </div>
      </div>

      {isLoading ? null : isError || !data ? (
        <div className="py-12 text-sm text-destructive">
          Failed to load articles.
        </div>
      ) : articles.length === 0 ? (
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
            <ArticleRow
              key={article.id}
              article={article}
              onTagClick={(t) => {
                setTag(t.slug, t.name)
                window.scrollTo({ top: 0 })
              }}
            />
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t pt-4">
        <p className="font-wire text-xs text-muted-foreground">
          {!isFetching && articles.length > 0
            ? `${articles.length} article${articles.length !== 1 ? "s" : ""}`
            : null}
        </p>
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
    </div>
  )
}
