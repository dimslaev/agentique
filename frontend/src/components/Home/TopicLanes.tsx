import { useQuery } from "@tanstack/react-query"

import { ArticlesService } from "@/client"
import { TopicLane } from "./TopicLane"
import type { TopicDef } from "./topics"

// The lane list is server-owned: `GET /articles/categories` returns every
// active category in `position` order. Re-ordering the homepage, renaming a
// lane, or retiring one is a DB change — this component renders whatever the
// vocabulary currently is.
export function TopicLanes() {
  const { data } = useQuery({
    queryKey: ["article-categories"],
    queryFn: () => ArticlesService.searchCategories({ limit: 50 }),
    staleTime: 60 * 60 * 1000,
  })

  const topics: TopicDef[] = (data ?? []).map((category) => ({
    slug: category.slug,
    label: category.name,
  }))

  return (
    <section className="w-full">
      <div className="grid items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {topics.map((topic) => (
          <TopicLane key={topic.slug} topic={topic} />
        ))}
      </div>
    </section>
  )
}
