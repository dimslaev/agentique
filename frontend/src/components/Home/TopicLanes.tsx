import { TopicLane } from "./TopicLane"
import { TOPICS } from "./topics"

export function TopicLanes() {
  return (
    <section className="w-full">
      <div className="grid items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TOPICS.map((topic) => (
          <TopicLane key={topic.slug} topic={topic} />
        ))}
      </div>
    </section>
  )
}
