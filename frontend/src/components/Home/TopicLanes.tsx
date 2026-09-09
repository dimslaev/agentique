import { SCORE_STANDOUT } from "@/components/Articles/ScoreRail"
import { TopicLane } from "./TopicLane"
import { TOPICS } from "./topics"

export function TopicLanes() {
  return (
    <section className="w-full pb-8">
      {/* Legend, not decoration: it is the only place the rail's colour rule
          is stated, so the bars mean something on first read. */}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-wire pb-3">
        <h2 className="font-wire text-[11px] uppercase tracking-[0.16em] text-paper">
          Today&apos;s wire
        </h2>
        <div className="flex items-center gap-5 font-wire text-[10px] uppercase tracking-[0.1em] text-dim">
          <span className="flex items-center gap-2">
            <span className="inline-block h-3 w-0.5 shrink-0 bg-signal" />
            scores {SCORE_STANDOUT}+
          </span>
          <span className="flex items-center gap-2">
            <span className="inline-block h-3 w-0.5 shrink-0 bg-paper/40" />
            bar height = score
          </span>
        </div>
      </div>
      <div className="grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
        {TOPICS.map((topic) => (
          <TopicLane key={topic.slug} topic={topic} />
        ))}
      </div>
    </section>
  )
}
