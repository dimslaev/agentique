import type { ArticlePublic } from "@/client"
import { ScoreRail } from "@/components/Articles/ScoreRail"
import { Skeleton } from "@/components/ui/skeleton"
import { useInView } from "@/hooks/useInView"
import { cn } from "@/lib/utils"
import type { TopicDef } from "./topics"
import { useTopicArticles } from "./useTopicArticles"

// Rows shown per box. The box fetches up to BOX_LIMIT so the thinner ones still
// fill all four; the rest are dropped, not paged.
const VISIBLE_ROWS = 4

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  })
}

export function TopicLane({
  topic,
  className,
}: {
  topic: TopicDef
  className?: string
}) {
  const { ref, inView } = useInView<HTMLDivElement>()
  const { articles, isPending, isError } = useTopicArticles(topic, inView)
  const visible = articles.slice(0, VISIBLE_ROWS)

  return (
    <div
      ref={ref}
      data-testid={`topic-lane-${topic.slug}`}
      className={cn("flex flex-col border-t border-wire pt-4", className)}
    >
      <div className="flex h-14 shrink-0 flex-col justify-start gap-1">
        <h2 className="line-clamp-1 font-display text-[13px] font-bold uppercase tracking-[0.1em] text-paper">
          {topic.label}
        </h2>
        <p className="line-clamp-2 text-xs leading-snug text-dim">
          {topic.blurb}
        </p>
      </div>

      <ul className="flex h-[26rem] flex-col">
        {isPending ? (
          <LaneSkeleton />
        ) : articles.length === 0 ? (
          <li className="flex h-full items-center text-sm text-dim">
            {isError ? "Couldn't load this one." : "Nothing new here yet."}
          </li>
        ) : (
          visible.map((article) => (
            <LaneRow key={article.id} article={article} />
          ))
        )}
      </ul>
    </div>
  )
}

function LaneRow({ article }: { article: ArticlePublic }) {
  return (
    <li className="group flex h-26 shrink-0 gap-3 border-b border-wire py-3 last:border-b-0">
      <ScoreRail score={article.score} />
      <div className="flex min-w-0 flex-1 flex-col justify-center">
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          className="line-clamp-2 text-sm font-medium leading-snug text-paper no-underline transition-colors hover:text-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
        >
          {article.title}
        </a>
        <div className="mt-1.5 flex items-center gap-1.5 overflow-hidden font-wire text-[10px] uppercase tracking-[0.08em] text-dim">
          <span className="truncate">{article.publisher.name}</span>
          <span className="shrink-0">/</span>
          <span className="shrink-0">{article.kind}</span>
          {article.published_at && (
            <span className="ml-auto shrink-0 tabular-nums normal-case">
              {formatDate(article.published_at)}
            </span>
          )}
        </div>
      </div>
    </li>
  )
}

function LaneSkeleton() {
  return (
    <>
      {Array.from({ length: VISIBLE_ROWS }, (_, i) => (
        <li
          key={i}
          className="flex h-26 shrink-0 gap-3 border-b border-wire py-3 last:border-b-0"
        >
          <div className="w-px shrink-0 self-stretch bg-wire" />
          <div className="flex flex-1 flex-col justify-center gap-2">
            <Skeleton className="h-3.5 w-full bg-wire" />
            <Skeleton className="h-3.5 w-2/3 bg-wire" />
            <Skeleton className="mt-1 h-2 w-24 bg-wire" />
          </div>
        </li>
      ))}
    </>
  )
}
