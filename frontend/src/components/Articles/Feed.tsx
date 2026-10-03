import { InlineSubscribe } from "@/components/Newsletter/InlineSubscribe"
import { SponsorRow } from "@/components/Sponsors/SponsorRow"
import { ArticlesList } from "./ArticlesList"
import { FeedFilters } from "./FeedFilters"

export function Feed() {
  return (
    <>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 pb-5">
        <InlineSubscribe />
        <h1 className="font-wire text-xs text-dim">AI news for builders</h1>
      </div>
      <SponsorRow />
      <FeedFilters />
      <ArticlesList />
    </>
  )
}
