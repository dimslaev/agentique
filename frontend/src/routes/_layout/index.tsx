import { createFileRoute } from "@tanstack/react-router"
import { Feed } from "@/components/Articles/Feed"

export const Route = createFileRoute("/_layout/")({
  component: Feed,
  head: () => ({
    meta: [{ title: "Agentique - AI news for developers" }],
  }),
})
