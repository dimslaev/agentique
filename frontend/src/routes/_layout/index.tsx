import { createFileRoute } from "@tanstack/react-router"
import { Feed } from "@/components/Articles/Feed"

export const Route = createFileRoute("/_layout/")({
  component: Feed,
  // The feed sets its own width: the column plus side rails.
  staticData: { wide: true },
  head: () => ({
    meta: [{ title: "Agentique - AI news for developers" }],
  }),
})
