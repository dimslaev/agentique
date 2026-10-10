import { useQuery } from "@tanstack/react-query"
import { ArticlesService, type OriginCounts } from "@/client"
import { cutoffIso, PUBLISHED_DAYS } from "@/components/Articles/ArticlesList"
import { ORIGIN_OPTIONS } from "@/components/Articles/FeedFilters"
import { useFilters } from "@/context/filters"
import { cn } from "@/lib/utils"

const LABELS = Object.fromEntries(ORIGIN_OPTIONS.map((o) => [o.value, o.label]))

function shortDate(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

/** How the wire's current window splits by origin, and how it was found.
 *  Follows the feed's Published filter; a row sets the From filter. */
export function WhoWrote() {
  const { filters, setFilter } = useFilters()
  const { dateRange, origin, search } = filters
  const days = PUBLISHED_DAYS[dateRange] ?? 7

  const { data, isError } = useQuery({
    queryKey: ["articles", "origins", dateRange],
    queryFn: () => ArticlesService.articleOrigins({ since: cutoffIso(days) }),
    staleTime: 5 * 60 * 1000,
  })

  const start = new Date()
  start.setDate(start.getDate() - days)

  return (
    // A search is all-time, so the window doesn't apply to it; greyed out
    // like the filters.
    <div
      inert={!!search}
      className={cn("flex flex-col gap-3", search && "opacity-40")}
    >
      <p className="font-wire text-[10px] tracking-[0.06em] text-dim">
        {shortDate(start)} – {shortDate(new Date())}
      </p>
      {isError ? (
        <p className="text-xs text-destructive">Failed to load.</p>
      ) : data ? (
        <Counts
          data={data}
          active={origin}
          onPick={(value) => setFilter("origin", value === origin ? "" : value)}
        />
      ) : null}
    </div>
  )
}

function Counts({
  data,
  active,
  onPick,
}: {
  data: OriginCounts
  active: string
  onPick: (origin: string) => void
}) {
  // Busiest first; a tie keeps the From filter's order.
  const rows = [...data.origins].sort((a, b) => b.count - a.count)
  const max = Math.max(1, data.unlabelled, ...rows.map((r) => r.count))

  return (
    <ul className="flex flex-col">
      {rows.map((r) => (
        <li key={r.origin}>
          <button
            type="button"
            aria-pressed={r.origin === active}
            onClick={() => onPick(r.origin)}
            className="group w-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <Row
              label={LABELS[r.origin] ?? r.origin}
              count={r.count}
              max={max}
              active={r.origin === active}
            />
          </button>
        </li>
      ))}
      {data.unlabelled > 0 && (
        <li>
          <Row
            label="Unlabelled"
            count={data.unlabelled}
            max={max}
            active={false}
          />
        </li>
      )}
    </ul>
  )
}

function Row({
  label,
  count,
  max,
  active,
}: {
  label: string
  count: number
  max: number
  active: boolean
}) {
  return (
    <span className="grid grid-cols-[76px_1fr_28px] items-center gap-2.5 py-1 text-left">
      <span
        className={cn(
          "truncate text-[13px] transition-colors",
          active
            ? "font-medium text-foreground"
            : "text-muted-foreground group-hover:text-foreground",
        )}
      >
        {label}
      </span>
      <span aria-hidden className="block h-2 bg-foreground/8">
        <span
          className={cn(
            "block h-full",
            active ? "bg-foreground" : "bg-foreground/45",
          )}
          style={{ width: `${(count / max) * 100}%` }}
        />
      </span>
      <span className="text-right font-wire text-xs tabular-nums">{count}</span>
    </span>
  )
}
