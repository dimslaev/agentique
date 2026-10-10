import { useQuery } from "@tanstack/react-query"
import { type ArticlePublic, ArticlesService } from "@/client"
import { cutoffIso } from "@/components/Articles/ArticlesList"
import { LikeButton } from "@/components/Articles/LikeButton"
import { articleClickHandlers } from "@/lib/analytics"
import { MiniRail } from "../ScoreMarks"

// Likes are sparse (most liked articles have one or two), so a week would
// often be empty.
const WINDOW_DAYS = 30
const SHOWN = 6

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  })
}

/** What readers liked most lately, beside what the agent scored it. */
export function ReaderPicks() {
  // The key starts with "articles" so LikeButton's optimistic patch reaches
  // it: a like here shows in the feed, and the other way round.
  const { data } = useQuery({
    queryKey: ["articles", "reader-picks"],
    queryFn: () =>
      ArticlesService.readArticles({
        sort: "likes-desc",
        since: cutoffIso(WINDOW_DAYS),
        limit: 20,
      }),
    staleTime: 5 * 60 * 1000,
  })

  const rows = (data?.data ?? [])
    .filter((a) => (a.like_count ?? 0) > 0)
    .slice(0, SHOWN)
  if (rows.length === 0) return null

  return (
    <ul data-testid="reader-picks" className="flex flex-col gap-3">
      {rows.map((a) => (
        <Row key={a.id} article={a} />
      ))}
    </ul>
  )
}

function Row({ article }: { article: ArticlePublic }) {
  return (
    <li data-testid="reader-pick" className="flex gap-2.5">
      <MiniRail score={article.score} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate font-wire text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
          {article.publisher.name}
          {article.published_at && ` · ${shortDate(article.published_at)}`}
        </span>
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          {...articleClickHandlers(article, { surface: "reader_picks" })}
          className="text-[13px] leading-snug no-underline decoration-muted-foreground underline-offset-[3px] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          {article.title}
        </a>
      </div>
      <div className="shrink-0 self-start pt-0.5">
        <LikeButton article={article} />
      </div>
    </li>
  )
}
