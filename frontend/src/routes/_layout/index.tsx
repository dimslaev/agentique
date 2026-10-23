import { createFileRoute } from "@tanstack/react-router"
import { ArticlesList, FeedFilters, FiltersProvider } from "@/features/feed"
import { SignupPanel } from "@/features/sign-in"
import { isLoggedIn } from "@/shared/auth"
import { RailsLayout } from "@/widgets/rails"

export const Route = createFileRoute("/_layout/")({
  component: Feed,
  // The feed sets its own width: the column plus side rails.
  staticData: { wide: true },
  head: () => ({
    meta: [{ title: "agentique — AI news for builders" }],
  }),
})

// Only the feed reads the filters, so they reset when the reader leaves it.
function Feed() {
  return (
    <FiltersProvider>
      <RailsLayout>
        {/* A signed-in reader already has an account and the newsletter. */}
        {!isLoggedIn() && <SignupPanel />}
        <FeedFilters />
        <ArticlesList />
      </RailsLayout>
    </FiltersProvider>
  )
}
