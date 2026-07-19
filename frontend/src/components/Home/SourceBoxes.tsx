import { useCallback, useEffect, useRef, useState } from "react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { type Source, SOURCES } from "./sources"

function monogram(name: string): string {
  return name
    .replace(/[^a-zA-Z]/g, "")
    .slice(0, 2)
    .toLowerCase()
}

function faviconUrl(domain: string): string {
  return `https://www.google.com/s2/favicons?sz=64&domain=${domain}`
}

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  })
}

export function SourceBoxes() {
  return (
    <section className="w-full">
      <div className="grid items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SOURCES.map((source) => (
          <SourceCard key={source.slug} source={source} />
        ))}
      </div>
    </section>
  )
}

function SourceCard({ source }: { source: Source }) {
  const listRef = useRef<HTMLUListElement>(null)
  // macOS Safari ignores ::-webkit-scrollbar styling on overlay scrollbars,
  // so the thin scrollbar alone isn't a reliable cue there. This fade is an
  // OS-independent fallback: shown whenever the list actually overflows
  // below the fold, hidden once scrolled to the end.
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
    <div className="relative flex h-[26rem] flex-col rounded-lg border bg-card py-4">
      <div className="flex shrink-0 items-center gap-3 px-4">
        <Avatar className="size-9 rounded-md border">
          <AvatarImage src={faviconUrl(source.domain)} alt={source.name} />
          <AvatarFallback className="rounded-md font-mono text-sm lowercase">
            {monogram(source.name)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <div className="truncate font-medium leading-tight">
            {source.name}
          </div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {source.label}
          </div>
        </div>
      </div>

      <ul
        ref={listRef}
        onScroll={updateFade}
        className="mt-2 min-h-0 flex-1 divide-y overflow-y-auto scrollbar-thin"
      >
        {source.articles.map((article) => (
          <li key={article.url} className="px-4 py-3">
            {article.from && (
              <div className="mb-1 flex items-center gap-1.5">
                {article.fromDomain && (
                  <Avatar className="size-3.5 rounded-sm">
                    <AvatarImage
                      src={faviconUrl(article.fromDomain)}
                      alt={article.from}
                    />
                    <AvatarFallback className="rounded-sm text-[8px]">
                      {monogram(article.from)}
                    </AvatarFallback>
                  </Avatar>
                )}
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  {article.from}
                </span>
              </div>
            )}
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
                {article.category}
              </span>
              {article.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground"
                >
                  {tag}
                </span>
              ))}
              <span className="ml-auto font-mono text-[11px] text-muted-foreground">
                {formatDate(article.date)}
              </span>
            </div>
          </li>
        ))}
      </ul>
      {showFade && (
        <div className="pointer-events-none absolute inset-x-0 bottom-4 h-8 bg-gradient-to-t from-card to-transparent" />
      )}
    </div>
  )
}
