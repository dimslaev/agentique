import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { trackEvent } from "@/lib/analytics"

export const Route = createFileRoute("/_layout/developers")({
  component: DevelopersPage,
  head: () => ({
    meta: [{ title: "Developers API - Agentique" }],
  }),
})

const RESPONSE_SHAPE = `{
  "data": [
    {
      "id": 1,
      "title": "string",
      "url": "string",
      "published_at": "ISO datetime | null",
      "score": "integer",
      "summary": "string | null",
      "categories": ["string"],
      "kind": "string",
      "created_at": "ISO datetime | null",
      "publisher": {
        "id": 1,
        "slug": "string",
        "name": "string",
        "kind": "individual | company | community | media",
        "image": "string | null"
      },
      "tags": [{ "slug": "string", "name": "string" }],
      "like_count": "integer",
      "liked_by_me": "boolean"
    }
  ],
  "count": "integer"
}`

function DevelopersPage() {
  const [dialogOpen, setDialogOpen] = useState(false)

  function onUpgrade() {
    trackEvent("checkout_click", {
      plan: "pro",
      price: 10,
      source: "developers",
    })
    setDialogOpen(true)
  }

  return (
    <div className="space-y-10">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight">
          Pro plan
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Programmatic access to curated AI news. $10/mo.
        </p>

        <div className="mt-6">
          <Button onClick={onUpgrade}>Upgrade to Pro — $10/mo</Button>
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Coming soon</DialogTitle>
            <DialogDescription>
              The Pro API isn&apos;t live yet. We&apos;ll email you the moment
              it opens — thanks for the interest.
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>

      <div className="space-y-6">
        <EndpointCard
          method="GET"
          path="/api/v1/articles"
          description="List recent articles with optional filters."
          params={[
            {
              name: "since",
              description: "ISO date · optional · omit for all-time",
            },
            { name: "limit", description: "integer · 1-50 · default 20" },
            {
              name: "q",
              description: "string · optional · title/content match",
            },
            { name: "min_score", description: "integer · 1-100 · optional" },
            {
              name: "category",
              description: "models | dev | research · optional",
            },
            {
              name: "kind",
              description:
                "repo | paper | model | blog | product | announcement · optional",
            },
            { name: "tag", description: "tag slug · optional" },
            {
              name: "sort",
              description:
                "score-desc (default) | published_at-desc | likes-desc",
            },
          ]}
        />

        <EndpointCard
          method="GET"
          path="/api/v1/articles/search"
          description="Semantic search over articles using natural language."
          params={[
            {
              name: "q",
              description: "string · required · natural language query",
            },
            { name: "limit", description: "integer · 1-50 · default 20" },
          ]}
        />
      </div>

      <div className="space-y-3">
        <h2 className="font-wire text-xs uppercase tracking-[0.1em] text-muted-foreground">
          Response
        </h2>
        <CodeBlock code={RESPONSE_SHAPE} />
      </div>
    </div>
  )
}

function EndpointCard({
  method,
  path,
  description,
  params,
}: {
  method: string
  path: string
  description: string
  params: { name: string; description: string }[]
}) {
  return (
    <div className="rounded-lg border bg-card p-5 space-y-4">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-wire text-xs font-bold text-primary">
            {method}
          </span>
          <code className="font-wire text-sm text-foreground">{path}</code>
        </div>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>

      <dl className="space-y-2">
        {params.map(({ name, description: desc }) => (
          <div key={name} className="flex gap-4 text-xs">
            <dt className="font-wire text-foreground w-28 shrink-0">{name}</dt>
            <dd className="text-muted-foreground">{desc}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // noop
    }
  }

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      <div className="flex justify-end border-b px-4 py-2">
        <button
          type="button"
          onClick={copy}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3 font-wire text-xs leading-relaxed text-foreground">
        {code}
      </pre>
    </div>
  )
}
