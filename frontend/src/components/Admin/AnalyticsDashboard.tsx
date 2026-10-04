import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { AnalyticsService, type ReportRow } from "@/client"
import { FilterOption, FilterRow } from "@/components/Articles/FilterOption"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import { DailyChart } from "./DailyChart"
import { formatCount } from "./format"
import { type RankedRow, RankedTable } from "./RankedTable"

const WINDOWS = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: null, label: "All time" },
]

function ranked(rows: ReportRow[]): RankedRow[] {
  return rows.map((r) => ({ key: r.label, ...r }))
}

export function AnalyticsDashboard() {
  const { user } = useAuth()
  if (!user) return null
  // The report endpoint answers 403 to everyone else, and a 403 signs the
  // reader out, so the request is never made for them.
  if (!user.is_superuser) {
    return <p className="py-6 text-sm text-muted-foreground">Admins only.</p>
  }
  return <Report />
}

function Report() {
  const [days, setDays] = useState<number | null>(30)
  const { data, isError, isPlaceholderData } = useQuery({
    queryKey: ["analytics-report", days],
    queryFn: () => AnalyticsService.readReport({ days }),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight">
            Analytics
          </h1>
          <p className="text-muted-foreground">
            Outside readers only.
            {data &&
              ` Left out: ${formatCount(data.totals.admin_pageviews)} pageviews from your devices, ${formatCount(data.totals.bot_pageviews)} from bots.`}
          </p>
        </div>
        <FilterRow label="Window">
          {/* biome-ignore lint/a11y/useSemanticElements: a fieldset's default styling fights the flex row */}
          <div
            role="group"
            aria-label="Window"
            className="flex flex-wrap gap-0.5"
          >
            {WINDOWS.map((w) => (
              <FilterOption
                key={w.label}
                label={w.label}
                active={w.days === days}
                onClick={() => setDays(w.days)}
              />
            ))}
          </div>
        </FilterRow>
      </div>

      {isError && (
        <p className="text-sm text-destructive">Couldn't load the report.</p>
      )}

      {data && (
        <div
          data-testid="analytics-report"
          className={cn(
            "flex flex-col gap-10 transition-opacity",
            isPlaceholderData && "opacity-60",
          )}
        >
          <dl className="grid grid-cols-2 gap-px border border-border bg-border sm:grid-cols-4">
            <StatTile label="Visitors" value={data.totals.visitors} />
            <StatTile label="Pageviews" value={data.totals.pageviews} />
            <StatTile
              label="Returning"
              value={data.totals.returning_visitors}
              note="seen on 2+ days"
            />
            <StatTile
              label="Article clicks"
              value={data.totals.article_clicks}
            />
          </dl>

          <DailyChart days={data.daily} />

          <div className="grid gap-10 sm:grid-cols-2">
            <RankedTable
              title="Pages"
              labelHeading="Path"
              countHeading="Views"
              rows={ranked(data.pages)}
            />
            <RankedTable
              title="Referrers"
              labelHeading="Host"
              countHeading="Views"
              rows={ranked(data.referrers)}
            />
          </div>

          <RankedTable
            title="Clicked articles"
            labelHeading="Article"
            countHeading="Clicks"
            rows={data.articles.map((a) => ({
              key: a.article_id,
              label: a.title ?? `#${a.article_id} (deleted)`,
              count: a.clicks,
              visitors: a.visitors,
            }))}
          />

          <div className="grid gap-10 sm:grid-cols-2">
            <RankedTable
              title="Events"
              labelHeading="Event"
              countHeading="Count"
              rows={ranked(data.events)}
            />
            <RankedTable
              title="Devices"
              labelHeading="Device"
              countHeading="Views"
              rows={ranked(data.devices)}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function StatTile({
  label,
  value,
  note,
}: {
  label: string
  value: number
  note?: string
}) {
  return (
    <div className="flex flex-col gap-1 bg-background p-4">
      <dt className="font-wire text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
        {label}
      </dt>
      <dd className="font-display text-3xl font-semibold">
        {formatCount(value)}
      </dd>
      {note && <dd className="text-xs text-muted-foreground">{note}</dd>}
    </div>
  )
}
