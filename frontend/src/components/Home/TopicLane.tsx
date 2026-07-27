import { useCallback, useEffect, useRef, useState } from "react"

import type { ArticlePublic } from "@/client"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Skeleton } from "@/components/ui/skeleton"
import { useInView } from "@/hooks/useInView"
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

export function TopicLane({ topic }: { topic: TopicDef }) {
  const { ref, inView } = useInView<HTMLDivElement>()
  const { articles, isPending, isError } = useTopicArticles(topic, inView)

  const listRef = useRef<HTMLUListElement>(null)
  // macOS Safari ignores ::-webkit-scrollbar styling on overlay scrollbars, so
  // the thin scrollbar alone isn't a reliable cue. This fade is the
  // OS-independent fallback, shown only while content remains below the fold.
  const [showFade, setShowFade] = useState(false)

  const updateFade = useCallback(() => {
    const el = listRef.current
    if (!el) return
    setShowFade(el.scrollHeight - el.scrollTop - el.clientHeight > 4)
  }, [])

  useEffect(() => {
    updateFade()
    window.addEventListener("resize", updateFade)
    return () => window.removeEventListener("resize", updateFade)
  }, [updateFade])

  return (
    // The height is reserved before the query runs. Boxes load as they scroll
    // into view, so a card that sized itself from its contents would reflow the
    // grid under the reader on every scroll tick.
    <div
      ref={ref}
      data-testid={`topic-lane-${topic.slug}`}
      className="relative flex flex-col rounded-lg border bg-card py-4 md:h-[26rem]"
    >
      <div className="shrink-0 px-4">
        <div className="font-medium leading-tight">{topic.label}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {topic.blurb}
        </div>
      </div>

      <ul
        ref={listRef}
        onScroll={updateFade}
        className="mt-2 min-h-0 flex-1 divide-y overflow-visible scrollbar-thin md:overflow-y-auto"
      >
        {isPending ? (
          <LaneSkeleton />
        ) : (
          articles.map((article) => (
            <LaneRow key={article.id} article={article} />
          ))
        )}
      </ul>

      {/* Never unmount a thin or failed box: it would yank content out from
          under a reader who has already scrolled to it. Keep the slot, say
          what happened inside it. */}
      {!isPending && articles.length === 0 && (
        <p className="px-4 py-3 text-sm text-muted-foreground">
          {isError ? "Couldn't load this one." : "Nothing new here yet."}
        </p>
      )}

      {showFade && (
        <div className="pointer-events-none absolute inset-x-0 bottom-4 hidden h-8 bg-gradient-to-t from-card to-transparent md:block" />
      )}
    </div>
  )
}

function LaneRow({ article }: { article: ArticlePublic }) {
  return (
    <li className="px-4 py-3">
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
        className="text-sm font-medium leading-snug hover:underline"
      >
        {article.title}
      </a>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <span className="rounded-full bg-muted px-2 py-0.5 text-[11px]">
          {article.kind}
        </span>
        {article.tags?.slice(0, 2).map((tag) => (
          <span
            key={tag.slug}
            className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground"
          >
            {tag.name}
          </span>
        ))}
        {article.published_at && (
          <span className="ml-auto font-mono text-[11px] text-muted-foreground">
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
        <li key={i} className="px-4 py-3">
          <Skeleton className="h-2.5 w-20" />
          <Skeleton className="mt-2 h-4 w-full" />
          <Skeleton className="mt-1.5 h-4 w-2/3" />
        </li>
      ))}
    </>
  )
}
