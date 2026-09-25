import { createFileRoute } from "@tanstack/react-router"
import { Feed } from "@/components/Articles/Feed"

export const Route = createFileRoute("/_layout/feed")({
  component: Feed,
  head: () => ({
    meta: [{ title: "Feed - Agentique" }],
  }),
})
