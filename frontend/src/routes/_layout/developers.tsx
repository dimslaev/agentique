import { createFileRoute } from "@tanstack/react-router"
import { ApiReference, UpgradeButton } from "@/features/developer-api"

export const Route = createFileRoute("/_layout/developers")({
  component: DevelopersPage,
  head: () => ({
    meta: [{ title: "Developers API - Agentique" }],
  }),
})

function DevelopersPage() {
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
          <UpgradeButton />
        </div>
      </div>

      <ApiReference />
    </div>
  )
}
