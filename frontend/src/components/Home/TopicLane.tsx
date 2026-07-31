import { ChevronDown, ChevronUp } from "lucide-react"
import { useState } from "react"

import type { ArticlePublic } from "@/client"
import { ScoreRail } from "@/components/Articles/ScoreRail"
import { Skeleton } from "@/components/ui/skeleton"
import { useInView } from "@/hooks/useInView"
import { cn } from "@/lib/utils"
import type { TopicDef } from "./topics"
import { useTopicArticles } from "./useTopicArticles"

// Rows per page, and per box by default. Paging swaps which slice of
// `articles` renders — there's no scroll container, so mouse wheel, trackpad,
// and touch scroll can't fight the pager the way they did with scroll-snap.
const PAGE_SIZE = 3

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

  const [page, setPage] = useState(0)
  const pageCount = Math.max(1, Math.ceil(articles.length / PAGE_SIZE))
  // Clamp rather than reset in an effect: articles can shrink (fewer than
  // BOX_LIMIT results) after the page was already advanced.
  const currentPage = Math.min(page, pageCount - 1)
  const visible = articles.slice(
    currentPage * PAGE_SIZE,
    currentPage * PAGE_SIZE + PAGE_SIZE,
  )

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

      <ul
        key={currentPage}
        className="flex h-[19.5rem] flex-col animate-in fade-in duration-200"
      >
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

      <div className="flex h-8 shrink-0 items-center gap-1">
        <button
          type="button"
          aria-label={`Show earlier ${topic.label} items`}
          disabled={currentPage === 0}
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          className="flex h-6 w-6 items-center justify-center text-dim transition-colors hover:text-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal disabled:invisible"
        >
          <ChevronUp className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label={`Show more ${topic.label} items`}
          disabled={currentPage >= pageCount - 1}
          onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
          className="flex h-6 w-6 items-center justify-center text-dim transition-colors hover:text-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal disabled:invisible"
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
        {pageCount > 1 && (
          <span className="ml-1 font-wire text-[10px] tabular-nums text-dim">
            {currentPage + 1}/{pageCount}
          </span>
        )}
      </div>
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
      {Array.from({ length: PAGE_SIZE }, (_, i) => (
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
