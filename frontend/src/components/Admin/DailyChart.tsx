import { type KeyboardEvent, useState } from "react"
import type { ReportDay } from "@/client"
import { cn } from "@/lib/utils"
import { formatCount, formatDay } from "./format"

/** The axis top: twice a 1/2/5 step, so the midline lands on a round number. */
function axisTop(max: number): number {
  const half = max / 2
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(half, 1)))
  const step =
    [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= half) ??
    10 * magnitude
  return step * 2
}

function describe(day: ReportDay): string {
  return `${formatDay(day.day)}: ${formatCount(day.visitors)} visitors, ${formatCount(day.pageviews)} pageviews`
}

/**
 * Visitors per day as columns. Hovering a column or moving through the days
 * with the arrow keys shows that day's numbers above it; the table under the
 * chart carries all of them.
 */
export function DailyChart({ days }: { days: ReportDay[] }) {
  const [picked, setPicked] = useState<number | null>(null)
  const last = days.length - 1
  // The window can shrink under a picked day.
  const active = picked !== null && picked <= last ? picked : null
  const top = axisTop(Math.max(1, ...days.map((d) => d.visitors)))
  const ticks = [top, top / 2, 0]
  const current = active ?? last

  const onKeyDown = (e: KeyboardEvent) => {
    const moves: Record<string, number> = {
      ArrowLeft: Math.max(0, current - 1),
      ArrowRight: Math.min(last, current + 1),
      Home: 0,
      End: last,
    }
    if (e.key in moves) {
      e.preventDefault()
      setPicked(moves[e.key])
    }
  }

  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="font-wire text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
        Visitors per day
      </figcaption>
      <div className="grid grid-cols-[auto_1fr] gap-x-2">
        <div
          aria-hidden
          className="flex h-40 flex-col justify-between text-right font-wire text-[10px] tabular-nums leading-none text-muted-foreground"
        >
          {ticks.map((t) => (
            <span key={t}>{formatCount(t)}</span>
          ))}
        </div>
        <div
          role="slider"
          tabIndex={0}
          aria-label="Visitors per day"
          aria-valuemin={0}
          aria-valuemax={last}
          aria-valuenow={current}
          aria-valuetext={days.length > 0 ? describe(days[current]) : undefined}
          onKeyDown={onKeyDown}
          onFocus={() => setPicked((p) => p ?? last)}
          onBlur={() => setPicked(null)}
          onPointerLeave={() => setPicked(null)}
          className="relative h-40 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
        >
          {ticks.map((t) => (
            <div
              key={t}
              aria-hidden
              className="absolute inset-x-0 border-t border-border"
              style={{ bottom: `${(t / top) * 100}%` }}
            />
          ))}
          <div aria-hidden className="absolute inset-0 flex items-end">
            {days.map((d, i) => (
              // Slots tile the plot edge to edge, so the pointer is always
              // over one; the 2px between columns is the slot's padding.
              <div
                key={d.day}
                onPointerEnter={() => setPicked(i)}
                className={cn(
                  "flex h-full min-w-0 flex-1 items-end justify-center",
                  days.length <= 90 && "px-px",
                )}
              >
                <div
                  className={cn(
                    "w-full max-w-6 bg-primary transition-opacity",
                    active !== null && i !== active && "opacity-40",
                  )}
                  style={{ height: `${(d.visitors / top) * 100}%` }}
                />
              </div>
            ))}
          </div>
          {active !== null && (
            <Readout day={days[active]} index={active} count={days.length} />
          )}
        </div>
        <div />
        <div
          aria-hidden
          className="mt-1.5 flex justify-between font-wire text-[10px] text-muted-foreground"
        >
          <span>{days.length > 0 && formatDay(days[0].day)}</span>
          <span>{days.length > 1 && formatDay(days[last].day)}</span>
        </div>
      </div>
      <details className="text-sm">
        <summary className="w-fit cursor-pointer font-wire text-[10px] uppercase tracking-[0.1em] text-muted-foreground hover:text-foreground">
          Table
        </summary>
        <table className="mt-2 w-full font-wire text-xs tabular-nums">
          <thead className="text-muted-foreground">
            <tr className="border-b border-border">
              <th className="py-1 text-left font-normal">Day</th>
              <th className="py-1 text-right font-normal">Visitors</th>
              <th className="py-1 text-right font-normal">Pageviews</th>
            </tr>
          </thead>
          <tbody>
            {[...days].reverse().map((d) => (
              <tr key={d.day} className="border-b border-border/60">
                <td className="py-1">{formatDay(d.day)}</td>
                <td className="py-1 text-right">{formatCount(d.visitors)}</td>
                <td className="py-1 text-right">{formatCount(d.pageviews)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  )
}

function Readout({
  day,
  index,
  count,
}: {
  day: ReportDay
  index: number
  count: number
}) {
  const center = ((index + 0.5) / count) * 100
  // Near either edge the readout hangs inward instead of centring, so it never
  // runs off the chart.
  const align =
    center < 15
      ? "translate-x-0"
      : center > 85
        ? "-translate-x-full"
        : "-translate-x-1/2"
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute -top-2 z-10 flex -translate-y-full flex-col gap-0.5 whitespace-nowrap border border-border bg-background px-2.5 py-1.5 text-xs",
        align,
      )}
      style={{ left: `${center}%` }}
    >
      <span className="text-sm font-semibold text-foreground">
        {formatCount(day.visitors)} visitors
      </span>
      <span className="text-muted-foreground">
        {formatCount(day.pageviews)} pageviews · {formatDay(day.day)}
      </span>
    </div>
  )
}
