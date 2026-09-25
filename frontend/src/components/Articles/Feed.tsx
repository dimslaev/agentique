import { ArticlesList } from "./ArticlesList"
import { FeedFilters } from "./FeedFilters"

export function Feed() {
  return (
    <>
      <FeedFilters />
      <ArticlesList />
    </>
  )
}
