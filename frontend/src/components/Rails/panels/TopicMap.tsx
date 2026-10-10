import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { SCORE_STANDOUT } from "@/components/Articles/ScoreRail"
import { articleClickHandlers } from "@/lib/analytics"
import { cn } from "@/lib/utils"

// Built nightly on the box by `python -m pipeline.topic_map` and served as a
// static file, so this is a plain fetch and not the generated API client.
const TOPIC_MAP_URL = "/data/topic-map.json"
const VERSION = 1
// The job runs daily; a file this old means it has stopped, and a stale map
// is worse than none.
const MAX_AGE_MS = 3 * 24 * 60 * 60 * 1000

const W = 272
const H = 210
const PAD = 10
const DOT = 5
// A dot is small; the area that hovers and clicks it is not.
const HIT = 11

type Cluster = { id: number; label: string; x: number; y: number; size: number }
type Point = {
  id: number
  x: number
  y: number
  cluster: number
  score: number
  title: string
  url: string
  publisher: string
}
type TopicMapData = {
  v: number
  generated_at: string
  window_days: number
  since: string
  count: number
  clusters: Cluster[]
  points: Point[]
}

async function fetchTopicMap(): Promise<TopicMapData | null> {
  const res = await fetch(TOPIC_MAP_URL)
  if (!res.ok) return null
  try {
    return (await res.json()) as TopicMapData
  } catch {
    // The dev server answers a missing file with the SPA's index.html.
    return null
  }
}

function usable(data: TopicMapData | null | undefined): data is TopicMapData {
  if (!data || data.v !== VERSION || !data.points?.length) return false
  const age = Date.now() - Date.parse(data.generated_at)
  return Number.isFinite(age) && age <= MAX_AGE_MS
}

const px = (x: number) => PAD + x * (W - 2 * PAD)
const py = (y: number) => PAD + y * (H - 2 * PAD)

// A label chip's size in viewBox units: 9px mono with its tracking and padding.
const CHAR_W = 6.2
const CHIP_PAD = 8
const CHIP_H = 14
const GAP = 4

type Box = { x: number; y: number; w: number }

function overlaps(a: Box, b: Box) {
  return (
    Math.abs(a.x - b.x) < (a.w + b.w) / 2 + 2 &&
    Math.abs(a.y - b.y) < CHIP_H + 2
  )
}

/** Where each cluster's label goes: centred over its dots, kept inside the
 *  map, and moved below the dots or further up when a larger cluster's label
 *  already sits there. `y` is the chip's top edge. */
function placeLabels(clusters: Cluster[], points: Point[]): Map<number, Box> {
  const bounds = new Map<number, { top: number; bottom: number; x: number[] }>()
  for (const p of points) {
    const b = bounds.get(p.cluster) ?? { top: H, bottom: 0, x: [] }
    b.top = Math.min(b.top, py(p.y))
    b.bottom = Math.max(b.bottom, py(p.y))
    b.x.push(px(p.x))
    bounds.set(p.cluster, b)
  }
  const placed = new Map<number, Box>()
  const order = [...clusters].sort((a, b) => b.size - a.size || a.id - b.id)
  for (const c of order) {
    const b = bounds.get(c.id)
    if (!b) continue
    const w = c.label.length * CHAR_W + CHIP_PAD
    const mid = b.x.reduce((sum, x) => sum + x, 0) / b.x.length
    const x = Math.min(Math.max(mid, w / 2 + 2), W - w / 2 - 2)
    const above = b.top - DOT / 2 - GAP - CHIP_H
    const below = b.bottom + DOT / 2 + GAP
    const tries = [above, below, above - CHIP_H - 2, below + CHIP_H + 2]
      .map((y) => Math.min(Math.max(y, 2), H - CHIP_H - 2))
      .map((y) => ({ x, y, w }))
    const clear = (t: Box) =>
      [...placed.values()].every((other) => !overlaps(t, other))
    // Covering another cluster's dots is worse than sitting further away.
    const covers = (t: Box) =>
      points.some(
        (p) =>
          p.cluster !== c.id &&
          Math.abs(px(p.x) - t.x) < t.w / 2 + DOT / 2 &&
          py(p.y) > t.y - DOT / 2 &&
          py(p.y) < t.y + CHIP_H + DOT / 2,
      )
    const free = tries.find((t) => clear(t) && !covers(t)) ?? tries.find(clear)
    placed.set(c.id, free ?? tries[0])
  }
  return placed
}

/** Each recent article as a dot, grouped by meaning into labelled clusters. */
export function TopicMap() {
  const { data } = useQuery({
    queryKey: ["topic-map"],
    queryFn: fetchTopicMap,
    staleTime: 30 * 60 * 1000,
  })
  const [focus, setFocus] = useState<number | null>(null)
  const [hover, setHover] = useState<Point | null>(null)

  if (!usable(data)) return null

  const span = data.window_days <= 7 ? "this week" : "this month"
  const summary = `${data.count} articles in ${data.clusters.length} clusters: ${data.clusters
    .map((c) => `${c.label} (${c.size})`)
    .join(", ")}`

  const labels = placeLabels(data.clusters, data.points)

  return (
    <div data-testid="topic-map">
      <p className="mb-2 font-wire text-[10px] tracking-[0.06em] text-dim">
        {span} · {data.count}
      </p>
      <div className="relative" style={{ aspectRatio: `${W} / ${H}` }}>
        <svg
          role="img"
          aria-label={summary}
          viewBox={`0 0 ${W} ${H}`}
          className="absolute inset-0 size-full border bg-ink-2"
          onMouseLeave={() => setHover(null)}
        >
          {data.points.map((p) => {
            const dim = focus !== null && p.cluster !== focus
            return (
              <a
                key={p.id}
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
                tabIndex={-1}
                data-testid="topic-map-dot"
                {...articleClickHandlers(p, { surface: "topic_map" })}
                onMouseEnter={() => setHover(p)}
                className={cn(
                  "transition-opacity",
                  dim ? "opacity-15" : "opacity-100",
                )}
              >
                <title>{`${p.title} — ${p.publisher}`}</title>
                <rect
                  x={px(p.x) - HIT / 2}
                  y={py(p.y) - HIT / 2}
                  width={HIT}
                  height={HIT}
                  fill="transparent"
                />
                <rect
                  x={px(p.x) - DOT / 2}
                  y={py(p.y) - DOT / 2}
                  width={DOT}
                  height={DOT}
                  className={
                    p.score >= SCORE_STANDOUT ? "fill-signal" : "fill-paper/55"
                  }
                />
              </a>
            )
          })}
        </svg>

        {data.clusters.map((c) => {
          const on = focus === c.id
          const box = labels.get(c.id)
          if (!box) return null
          return (
            <button
              key={c.id}
              type="button"
              aria-pressed={on}
              aria-label={`Highlight ${c.label}, ${c.size} articles`}
              onClick={() => setFocus(on ? null : c.id)}
              className={cn(
                "absolute -translate-x-1/2 whitespace-nowrap bg-ink px-1 font-wire text-[9px] uppercase leading-[14px] tracking-[0.08em] transition-opacity focus-visible:outline-2 focus-visible:outline-primary",
                on ? "text-primary" : "text-paper",
                focus !== null && !on && "opacity-40",
              )}
              style={{
                left: `${(box.x / W) * 100}%`,
                top: `${(box.y / H) * 100}%`,
              }}
            >
              {c.label}
            </button>
          )
        })}

        {hover && (
          <div
            role="tooltip"
            className={cn(
              "pointer-events-none absolute z-10 w-max max-w-[200px] border bg-ink px-2 py-1.5 text-xs leading-snug shadow-[0_8px_24px_rgba(0,0,0,0.5)]",
              hover.x > 0.5 ? "-translate-x-full" : "",
              hover.y > 0.5 ? "-translate-y-full" : "",
            )}
            style={{
              left: `${((px(hover.x) + (hover.x > 0.5 ? -8 : 8)) / W) * 100}%`,
              top: `${((py(hover.y) + (hover.y > 0.5 ? -8 : 8)) / H) * 100}%`,
            }}
          >
            <span className="block">{hover.title}</span>
            <span className="mt-0.5 block font-wire text-[10px] text-dim">
              {hover.publisher}
            </span>
          </div>
        )}
      </div>

      <ul className="sr-only">
        {data.clusters.map((c) => (
          <li key={c.id}>
            {c.label}: {c.size} articles
          </li>
        ))}
      </ul>
    </div>
  )
}
