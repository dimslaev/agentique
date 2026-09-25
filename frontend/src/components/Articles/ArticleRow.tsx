import type { ArticlePublic, TagPublic } from "@/client"
import { LikeButton } from "./LikeButton"
import { ScoreRail } from "./ScoreRail"

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  })
}

export function ArticleRow({
  article,
  onTagClick,
}: {
  article: ArticlePublic
  /** Makes tags clickable. Without it (e.g. on the profile page, where there
   *  is no feed to filter) tags render as plain text. */
  onTagClick?: (tag: TagPublic) => void
}) {
  return (
    <li
      data-testid="article-row"
      className="group flex gap-3 border-b border-border py-4 last:border-b-0"
    >
      <ScoreRail score={article.score} />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex items-center gap-1.5 overflow-hidden font-wire text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
          <span className="truncate">{article.publisher.name}</span>
          <span className="shrink-0">/</span>
          <span className="shrink-0">{article.kind}</span>
          {article.published_at && (
            <span className="ml-auto shrink-0 pl-2 tabular-nums normal-case">
              {formatDate(article.published_at)}
            </span>
          )}
        </div>
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          className="font-medium leading-snug no-underline decoration-muted-foreground underline-offset-[3px] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          {article.title}
        </a>
        <div className="flex items-center gap-3">
          {article.tags && article.tags.length > 0 && (
            <div className="flex min-w-0 flex-wrap gap-x-3 gap-y-0.5 font-wire text-[11px] text-muted-foreground">
              {article.tags.map((tag) =>
                onTagClick ? (
                  <button
                    key={tag.slug}
                    type="button"
                    onClick={() => onTagClick(tag)}
                    className="transition-colors hover:text-foreground"
                  >
                    #{tag.slug}
                  </button>
                ) : (
                  <span key={tag.slug}>#{tag.slug}</span>
                ),
              )}
            </div>
          )}
          <div className="ml-auto shrink-0">
            <LikeButton article={article} />
          </div>
        </div>
      </div>
    </li>
  )
}
