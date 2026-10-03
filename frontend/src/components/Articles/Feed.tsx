import { SignupPanel } from "@/components/Auth/SignupPanel"
import { isLoggedIn } from "@/hooks/useAuth"
import { ArticlesList } from "./ArticlesList"
import { FeedFilters } from "./FeedFilters"

export function Feed() {
  return (
    <>
      {/* A signed-in reader already has an account and the newsletter. */}
      {!isLoggedIn() && <SignupPanel />}
      <FeedFilters />
      <ArticlesList />
    </>
  )
}
