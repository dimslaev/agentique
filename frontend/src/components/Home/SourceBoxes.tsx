import { type Source, SOURCES } from "./sources"

function monogram(name: string): string {
  return name.replace(/[^a-zA-Z]/g, "").slice(0, 2).toLowerCase()
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
      <div className="mb-6 flex flex-col gap-1">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          The sources
        </p>
        <h2 className="text-xl font-semibold tracking-tight">
          One box per source. Straight to the original.
        </h2>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SOURCES.map((source) => (
          <SourceCard key={source.slug} source={source} />
        ))}
      </div>
    </section>
  )
}

function SourceCard({ source }: { source: Source }) {
  return (
    <div className="flex flex-col rounded-lg border bg-card p-4">
      <div className="flex items-center gap-3">
        {/* Monogram square echoes the "ag" wordmark: mono, lowercase, boxed. */}
        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border font-mono text-sm lowercase text-foreground">
          {monogram(source.name)}
        </span>
        <div className="min-w-0">
          <div className="truncate font-medium leading-tight">{source.name}</div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {source.label}
          </div>
        </div>
      </div>

      <ul className="mt-2 divide-y">
        {source.articles.map((article) => (
          <li key={article.url} className="py-3">
            {article.from && (
              <div className="mb-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                {article.from}
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
    </div>
  )
}
