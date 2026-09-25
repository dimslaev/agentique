// Unused page: kept for now but hidden from nav (not linked from the header).
// The route, the /api/subscribe backend endpoint, and SubscribeForm all remain.
import { createFileRoute } from "@tanstack/react-router"

import { SubscribeForm } from "@/components/Newsletter/SubscribeForm"
import { Separator } from "@/components/ui/separator"

export const Route = createFileRoute("/_layout/newsletter")({
  component: Newsletter,
  head: () => ({
    meta: [{ title: "Newsletter - Agentique" }],
  }),
})

function Newsletter() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight">
          Every AI story that matters. For devs.
        </h1>
        <p className="text-muted-foreground mt-2">
          Agentique ingests 1,000+ articles, tweets, and discussions every day
          and runs them through an AI pipeline trained to answer one question:
          can a developer act on this today?
        </p>
      </div>

      <SubscribeForm />

      <Separator />

      <section>
        <h2 className="font-wire text-muted-foreground text-xs tracking-[0.1em] uppercase">
          Who it&apos;s for
        </h2>
        <p className="mt-3 text-sm">
          You&apos;re building with AI. Read Agentique with your morning coffee
          and walk into your day already knowing what shipped.
        </p>
        <p className="text-muted-foreground mt-2 text-sm">
          Most AI newsletters cover the business of AI. Agentique covers the
          craft - tools, models, techniques, and code.
        </p>
        <ul className="mt-4 list-disc space-y-1.5 pl-5 text-sm">
          <li>Discover tools you can open a terminal and try today.</li>
          <li>Pick up novel agent orchestration patterns.</li>
          <li>
            Know which model is right for which task before your next project.
          </li>
          <li>Be the go-to person in your team about AI.</li>
        </ul>
      </section>

      <Separator />

      <section>
        <h2 className="font-wire text-muted-foreground text-xs tracking-[0.1em] uppercase">
          The sources
        </h2>
        <p className="mt-3 text-sm">
          We spend considerable time curating the places where builders and
          researchers actually share what they&apos;re working on.
        </p>
        <ul className="mt-4 list-disc space-y-1.5 pl-5 text-sm">
          <li>Every major AI newsletter.</li>
          <li>Hacker News and Reddit&apos;s AI communities.</li>
          <li>Discord servers where researchers talk in real time.</li>
          <li>
            Curated X/Twitter lists spanning tens of thousands of accounts.
          </li>
          <li>
            GitHub profiles of the most prolific AI builders and research teams.
          </li>
        </ul>
      </section>

      <Separator />

      <section>
        <h2 className="font-wire text-muted-foreground text-xs tracking-[0.1em] uppercase">
          The pipeline
        </h2>
        <p className="mt-3 text-sm">
          Every piece of content passes through a multi-stage AI pipeline before
          it reaches the feed.
        </p>
        <ul className="mt-4 list-disc space-y-1.5 pl-5 text-sm">
          <li>Semantic deduplication across all sources.</li>
          <li>Deep relevance and actionability scoring.</li>
          <li>LLM-powered context enrichment and summarization.</li>
        </ul>
      </section>
    </div>
  )
}
