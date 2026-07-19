import { createFileRoute } from "@tanstack/react-router"
import { ArticlesList } from "@/components/Articles/ArticlesList"

export const Route = createFileRoute("/_layout/feed")({
  component: ArticlesList,
  head: () => ({
    meta: [{ title: "Feed - Agentique" }],
  }),
})
