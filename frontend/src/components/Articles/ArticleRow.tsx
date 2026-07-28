import type { ArticlePublic } from "@/client"
import { LikeButton } from "./LikeButton"

export function ArticleRow({ article }: { article: ArticlePublic }) {
  return (
    <li data-testid="article-row" className="py-5">
      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
        <span>{article.publisher.name}</span>
        {article.published_at && (
          <>
            <span>·</span>
            <span>
              {new Date(article.published_at).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              })}
            </span>
          </>
        )}
        {article.kind && (
          <>
            <span>·</span>
            <span>{article.kind}</span>
          </>
        )}
      </div>
      <a
        href={article.url ?? "#"}
        target="_blank"
        rel="noreferrer"
        className="font-medium hover:underline"
      >
        {article.title}
      </a>
      {article.summary && (
        <p className="mt-1 text-sm text-muted-foreground line-clamp-3">
          {article.summary}
        </p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {article.categories && article.categories.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {article.categories.map((category) => (
              <span
                key={category.slug}
                className="text-xs px-2 py-0.5 rounded-full bg-muted"
              >
                {category.name}
              </span>
            ))}
          </div>
        )}
        <LikeButton article={article} />
      </div>
    </li>
  )
}
