import { createFileRoute } from "@tanstack/react-router"
import { Feed } from "@/components/Articles/Feed"
import { FiltersProvider } from "@/features/feed"

export const Route = createFileRoute("/_layout/")({
  component: FeedPage,
  // The feed sets its own width: the column plus side rails.
  staticData: { wide: true },
  head: () => ({
    meta: [{ title: "agentique — AI news for builders" }],
  }),
})

// Only the feed reads the filters, so they reset when the reader leaves it.
function FeedPage() {
  return (
    <FiltersProvider>
      <Feed />
    </FiltersProvider>
  )
}
