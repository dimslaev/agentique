import { RailsLayout } from "@/components/Rails/RailsLayout"
import { ArticlesList, FeedFilters } from "@/features/feed"
import { SignupPanel } from "@/features/sign-in"
import { isLoggedIn } from "@/shared/auth"

export function Feed() {
  return (
    <RailsLayout>
      {/* A signed-in reader already has an account and the newsletter. */}
      {!isLoggedIn() && <SignupPanel />}
      <FeedFilters />
      <ArticlesList />
    </RailsLayout>
  )
}
