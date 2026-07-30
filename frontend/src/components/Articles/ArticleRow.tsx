import type { ArticlePublic } from "@/client"
import { LikeButton } from "./LikeButton"
import { ScoreRail } from "./ScoreRail"

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  })
}

export function ArticleRow({ article }: { article: ArticlePublic }) {
  return (
    <li
      data-testid="article-row"
      className="group flex gap-3 border-b border-border py-5 last:border-b-0"
    >
      <ScoreRail score={article.score} />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex items-center gap-1.5 overflow-hidden font-wire text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
          <span className="truncate">{article.publisher.name}</span>
          <span className="shrink-0">/</span>
          <span className="shrink-0">{article.kind}</span>
          {article.published_at && (
            <span className="ml-auto shrink-0 tabular-nums normal-case">
              {formatDate(article.published_at)}
            </span>
          )}
        </div>
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          className="font-medium leading-snug decoration-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          {article.title}
        </a>
        <div className="flex flex-wrap items-center gap-2 pt-0.5">
          {article.categories && article.categories.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {article.categories.map((cat) => (
                <span
                  key={cat}
                  className="border border-border px-1.5 py-0.5 font-wire text-[10px] uppercase tracking-wide text-muted-foreground"
                >
                  {cat}
                </span>
              ))}
            </div>
          )}
          {article.tags && article.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {article.tags.map((tag) => (
                <span
                  key={tag.slug}
                  className="border border-border px-1.5 py-0.5 font-wire text-[10px] uppercase tracking-wide text-muted-foreground"
                >
                  {tag.name}
                </span>
              ))}
            </div>
          )}
          <LikeButton article={article} />
        </div>
      </div>
    </li>
  )
}
