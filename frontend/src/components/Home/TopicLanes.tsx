import { TopicLane } from "./TopicLane"
import { TOPICS } from "./topics"

// TOPICS.length % 3 === 1 leaves a single box alone on the last row at the
// 3-column breakpoint — center it in the middle column instead of letting it
// hug the left edge.
const lastAlone = TOPICS.length % 3 === 1

export function TopicLanes() {
  return (
    <section className="w-full">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {TOPICS.map((topic, i) => (
          <TopicLane
            key={topic.slug}
            topic={topic}
            className={
              lastAlone && i === TOPICS.length - 1 ? "lg:col-start-2" : undefined
            }
          />
        ))}
      </div>
    </section>
  )
}
