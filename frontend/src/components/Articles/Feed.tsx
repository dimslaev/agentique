import { SignupPanel } from "@/components/Auth/SignupPanel"
import { SponsorRow } from "@/components/Sponsors/SponsorRow"
import { isLoggedIn } from "@/hooks/useAuth"
import { ArticlesList } from "./ArticlesList"
import { FeedFilters } from "./FeedFilters"

export function Feed() {
  return (
    <>
      {/* A signed-in reader already has an account and the newsletter. */}
      {!isLoggedIn() && <SignupPanel />}
      <SponsorRow />
      <FeedFilters />
      <ArticlesList />
    </>
  )
}
