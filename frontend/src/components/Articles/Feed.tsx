import { SignupPanel } from "@/components/Auth/SignupPanel"
import { RailsLayout } from "@/components/Rails/RailsLayout"
import { isLoggedIn } from "@/hooks/useAuth"
import { ArticlesList } from "./ArticlesList"
import { FeedFilters } from "./FeedFilters"

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
