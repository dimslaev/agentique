import { useQuery } from "@tanstack/react-query"
import { type ArticlePublic, ArticlesService } from "@/client"
import { cutoffIso } from "@/components/Articles/ArticlesList"
import { LikeButton } from "@/components/Articles/LikeButton"
import { articleClickHandlers } from "@/lib/analytics"
import { RailRow } from "../RailRow"

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
    <RailRow
      testId="reader-pick"
      score={article.score}
      source={article.publisher.name}
      date={article.published_at ? shortDate(article.published_at) : undefined}
      title={article.title}
      href={article.url}
      linkProps={articleClickHandlers(article, { surface: "reader_picks" })}
      trailing={<LikeButton article={article} />}
    />
  )
}
