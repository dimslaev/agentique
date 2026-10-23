import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useFilters } from "@/context/filters"
import { ArticlesService, type Voice, type VoiceKind } from "@/shared/api"
import { trackEvent } from "@/shared/lib/analytics"
import { cutoffIso } from "@/shared/lib/published"
import { cn } from "@/shared/lib/utils"
import { FilterOption } from "@/shared/ui/filter-option"
import { ScoreBars } from "../ScoreMarks"

// Fixed, not the feed's window: over 3 days most names have one article or
// none, and a row of bars says nothing.
const WINDOW_DAYS = 30

const TABS: { value: VoiceKind; label: string }[] = [
  { value: "individual", label: "Writers" },
  { value: "lab", label: "Labs" },
  { value: "company", label: "Companies" },
]

/** Who writes the wire: each name with a bar per article, oldest to newest,
 *  and its best one. A row filters the feed to that publisher. */
export function Voices() {
  const { filters, setFilter } = useFilters()
  const { publisher, search } = filters
  const [kind, setKind] = useState<VoiceKind>("individual")

  const { data, isError } = useQuery({
    queryKey: ["articles", "voices", kind],
    queryFn: () =>
      ArticlesService.articleVoices({ kind, since: cutoffIso(WINDOW_DAYS) }),
    staleTime: 5 * 60 * 1000,
    placeholderData: keepPreviousData,
  })
  if (isError || !data) return null

  function pick(voice: Voice) {
    if (voice.slug === publisher) {
      setFilter("publisher", "")
      setFilter("publisherName", "")
      return
    }
    trackEvent("voices_pick", { publisher: voice.slug, kind })
    setFilter("publisher", voice.slug)
    setFilter("publisherName", voice.name)
    // The feed shows what the row counted: the same month, and for a writer
    // posts only (Writers is that From option), not their repos and models.
    setFilter("dateRange", "1m")
    setFilter("origin", kind === "individual" ? "individual" : "")
  }

  return (
    // A search is all-time and ignores the publisher; greyed out like the
    // filters.
    <div
      inert={!!search}
      className={cn("flex flex-col gap-2", search && "opacity-40")}
    >
      {/* biome-ignore lint/a11y/useSemanticElements: a fieldset's default styling fights the flex row */}
      <div role="group" aria-label="Voices" className="-ml-1.5 flex gap-0.5">
        {TABS.map((t) => (
          <FilterOption
            key={t.value}
            label={t.label}
            active={t.value === kind}
            onClick={() => setKind(t.value)}
          />
        ))}
      </div>
      {data.length === 0 ? (
        <p className="text-xs text-dim">Nobody here in the last 30 days.</p>
      ) : (
        <ul data-testid="voices" className="flex flex-col">
          {data.map((v) => (
            <li key={v.slug}>
              <Row
                voice={v}
                active={v.slug === publisher}
                onPick={() => pick(v)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Row({
  voice,
  active,
  onPick,
}: {
  voice: Voice
  active: boolean
  onPick: () => void
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onPick}
      data-testid="voice"
      className="group grid w-full grid-cols-[1fr_auto_28px] items-center gap-x-2.5 gap-y-0.5 py-1.5 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
    >
      <span
        data-testid="voice-name"
        className={cn(
          "truncate text-[13px] font-medium decoration-1 underline-offset-[5px] group-hover:underline",
          active && "underline",
        )}
      >
        {voice.name}
      </span>
      <ScoreBars scores={voice.scores} />
      <span className="text-right font-wire text-xs tabular-nums">
        {voice.count}
      </span>
      <span className="col-span-2 truncate text-xs text-dim">
        {voice.best.title}
      </span>
      <span className="text-right font-wire text-xs tabular-nums text-dim">
        {voice.best.score}
      </span>
    </button>
  )
}
