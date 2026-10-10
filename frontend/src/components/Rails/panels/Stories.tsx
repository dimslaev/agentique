import { useQuery } from "@tanstack/react-query"
import { useId, useState } from "react"
import { StoriesService, type StoryPublic } from "@/client"
import { articleClickHandlers, trackEvent } from "@/lib/analytics"
import { cn } from "@/lib/utils"
import { RailMeta } from "../RailMeta"
import { RailRow } from "../RailRow"
import { ScoreBars } from "../ScoreMarks"

export const STORIES_PANEL_ID = "stories"

// The timeline shows this many; "Show all" opens the rest in place.
const TIMELINE = 6
// Enough bars to read a story's shape without crowding its name.
const BARS = 12

export function useStories() {
  return useQuery({
    queryKey: ["stories"],
    queryFn: () => StoriesService.readStories({ limit: 5 }),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}

/** Whether there is anything to show. An empty list, a failed fetch, or one
 *  still loading hides the panel, and the rail with it. */
export function useHasStories() {
  const { data } = useStories()
  return !!data && data.length > 0
}

function day(iso: string | null | undefined): string {
  if (!iso) return ""
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  })
}

function span(story: StoryPublic): string {
  const first = day(story.first_at)
  const last = day(story.last_at)
  return first === last ? last : `${first} – ${last}`
}

export function Stories() {
  const { data } = useStories()
  // undefined until the reader picks: the first story starts open.
  const [open, setOpen] = useState<string | null>()
  if (!data || data.length === 0) return null

  const current = open === undefined ? data[0].slug : open

  function toggle(slug: string) {
    const next = current === slug ? null : slug
    setOpen(next)
    if (next) trackEvent("story_open", { slug })
  }

  return (
    <ul data-testid="stories">
      {data.map((story) => (
        <StoryRow
          key={story.slug}
          story={story}
          open={current === story.slug}
          onToggle={() => toggle(story.slug)}
        />
      ))}
    </ul>
  )
}

function StoryRow({
  story,
  open,
  onToggle,
}: {
  story: StoryPublic
  open: boolean
  onToggle: () => void
}) {
  const bodyId = useId()
  const bars = story.articles
    .slice(0, BARS)
    .map((a) => a.score)
    .reverse()

  return (
    <li className="border-b last:border-b-0" data-testid="story">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={onToggle}
        data-testid="story-row"
        className="flex w-full items-start gap-3 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="font-display text-[15px] font-bold leading-tight [overflow-wrap:anywhere]">
              {story.name}
            </span>
            {story.grew_today && (
              <span
                role="img"
                aria-label="Grew today"
                className="size-1.5 shrink-0 bg-signal"
              />
            )}
          </span>
          <RailMeta className="mt-1">
            {span(story)} · {story.article_count}
          </RailMeta>
        </span>
        <ScoreBars scores={bars} className="mt-0.5" />
      </button>
      <div
        id={bodyId}
        data-testid="story-body"
        data-open={open}
        inert={!open}
        className={cn(
          "grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          <StoryBody story={story} />
        </div>
      </div>
    </li>
  )
}

function StoryBody({ story }: { story: StoryPublic }) {
  const [all, setAll] = useState(false)
  const shown = all ? story.articles : story.articles.slice(0, TIMELINE)
  const rest = story.articles.length - TIMELINE

  return (
    <div className="mb-4">
      <ol className="flex flex-col gap-3">
        {shown.map((article) => (
          <RailRow
            key={article.id}
            score={article.score}
            source={article.publisher}
            date={day(article.published_at)}
            title={article.title}
            href={article.url}
            linkProps={articleClickHandlers(article, {
              via: "story",
              story: story.slug,
            })}
          />
        ))}
      </ol>
      {rest > 0 && !all && (
        <button
          type="button"
          onClick={() => setAll(true)}
          className="mt-3 font-wire text-[11px] text-dim transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          Show all {story.articles.length}
        </button>
      )}
    </div>
  )
}
