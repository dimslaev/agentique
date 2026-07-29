import { ChevronDown, ChevronUp } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import type { ArticlePublic } from "@/client"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Skeleton } from "@/components/ui/skeleton"
import { useInView } from "@/hooks/useInView"
import { cn } from "@/lib/utils"
import { BOX_LIMIT, type TopicDef } from "./topics"
import { useTopicArticles } from "./useTopicArticles"

function monogram(name: string): string {
  return name
    .replace(/[^a-zA-Z]/g, "")
    .slice(0, 2)
    .toLowerCase()
}

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

  const listRef = useRef<HTMLUListElement>(null)
  const [canScrollUp, setCanScrollUp] = useState(false)
  const [canScrollDown, setCanScrollDown] = useState(false)

  const updateScrollState = useCallback(() => {
    const el = listRef.current
    if (!el) return
    setCanScrollUp(el.scrollTop > 4)
    setCanScrollDown(el.scrollHeight - el.scrollTop - el.clientHeight > 4)
  }, [])

  useEffect(() => {
    updateScrollState()
    window.addEventListener("resize", updateScrollState)
    return () => window.removeEventListener("resize", updateScrollState)
  }, [updateScrollState])

  // Content height changes once real rows replace the skeleton (or a lane
  // turns out to have fewer than BOX_LIMIT articles) — recompute then too,
  // not just on scroll and resize.
  useEffect(() => {
    updateScrollState()
  }, [articles, isPending, updateScrollState])

  const page = useCallback((direction: 1 | -1) => {
    const el = listRef.current
    if (!el) return
    const max = el.scrollHeight - el.clientHeight
    const target = Math.min(
      Math.max(el.scrollTop + direction * el.clientHeight, 0),
      max,
    )
    el.scrollTo({ top: target, behavior: "smooth" })
  }, [])

  return (
    <div
      ref={ref}
      data-testid={`topic-lane-${topic.slug}`}
      className={cn("flex flex-col rounded-xl border bg-card py-5", className)}
    >
      <div className="flex h-16 shrink-0 flex-col justify-center gap-0.5 px-5">
        <div className="line-clamp-1 font-medium leading-tight">
          {topic.label}
        </div>
        <div className="line-clamp-2 text-xs leading-snug text-muted-foreground">
          {topic.blurb}
        </div>
      </div>

      <ul
        ref={listRef}
        onScroll={updateScrollState}
        className="mt-2 flex h-[21rem] snap-y snap-mandatory flex-col overflow-y-auto scrollbar-thin"
      >
        {isPending ? (
          <LaneSkeleton />
        ) : articles.length === 0 ? (
          <li className="flex h-full items-center justify-center px-5 text-sm text-muted-foreground">
            {isError ? "Couldn't load this one." : "Nothing new here yet."}
          </li>
        ) : (
          articles.map((article) => (
            <LaneRow key={article.id} article={article} />
          ))
        )}
      </ul>

      <div className="mt-1 flex h-8 shrink-0 items-center justify-center gap-2">
        <button
          type="button"
          aria-label={`Show earlier ${topic.label} items`}
          disabled={!canScrollUp}
          onClick={() => page(-1)}
          className="flex h-6 w-6 items-center justify-center rounded-full border text-muted-foreground transition-colors hover:text-foreground disabled:invisible"
        >
          <ChevronUp className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label={`Show more ${topic.label} items`}
          disabled={!canScrollDown}
          onClick={() => page(1)}
          className="flex h-6 w-6 items-center justify-center rounded-full border text-muted-foreground transition-colors hover:text-foreground disabled:invisible"
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

function LaneRow({ article }: { article: ArticlePublic }) {
  return (
    <li className="flex h-28 shrink-0 snap-start flex-col justify-center overflow-hidden border-b px-5 last:border-b-0">
      <div className="mb-1 flex items-center gap-1.5">
        <Avatar className="size-3.5 rounded-sm">
          {article.publisher.image && (
            <AvatarImage
              src={article.publisher.image}
              alt={article.publisher.name}
            />
          )}
          <AvatarFallback className="rounded-sm text-[8px]">
            {monogram(article.publisher.name)}
          </AvatarFallback>
        </Avatar>
        <span className="truncate font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          {article.publisher.name}
        </span>
      </div>
      <a
        href={article.url}
        target="_blank"
        rel="noreferrer"
        className="line-clamp-2 text-sm font-medium leading-snug hover:underline"
      >
        {article.title}
      </a>
      <div className="mt-1.5 flex items-center gap-1.5 overflow-hidden text-[11px] uppercase tracking-wide text-muted-foreground">
        <span className="shrink-0">{article.kind}</span>
        {article.tags?.[0] && (
          <>
            <span className="shrink-0">·</span>
            <span className="truncate">{article.tags[0].name}</span>
          </>
        )}
        {article.published_at && (
          <span className="ml-auto shrink-0 font-mono normal-case">
            {formatDate(article.published_at)}
          </span>
        )}
      </div>
    </li>
  )
}

function LaneSkeleton() {
  return (
    <>
      {Array.from({ length: BOX_LIMIT }, (_, i) => (
        <li
          key={i}
          className="flex h-28 shrink-0 snap-start flex-col justify-center gap-1.5 border-b px-5 last:border-b-0"
        >
          <Skeleton className="h-2.5 w-20" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </li>
      ))}
    </>
  )
}
