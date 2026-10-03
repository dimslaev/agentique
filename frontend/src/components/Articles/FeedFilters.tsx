import { Search, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useFilters } from "@/context/filters"
import { cn } from "@/lib/utils"
import { FilterOptions, FilterRow } from "./FilterOption"
import { findTopic, TOPICS } from "./topics"

// Who published it, or what it is when that is settled. Each article falls
// under exactly one: a repo is a repo whoever published it.
const ORIGIN_OPTIONS = [
  { value: "", label: "All" },
  { value: "lab", label: "Labs" },
  { value: "company", label: "Companies" },
  { value: "individual", label: "Writers" },
  { value: "media", label: "Media" },
  { value: "repo", label: "Repos" },
  { value: "paper", label: "Papers" },
  { value: "model", label: "Models" },
]

const TOPIC_OPTIONS = [
  { value: "", label: "All" },
  ...TOPICS.map((t) => ({ value: t.slug, label: t.label })),
]

export function FeedFilters() {
  const { filters, setFilter } = useFilters()

  return (
    <>
      <MobileActiveFilters />
      {/* Hidden on phones, where it pushed the wire half a screen down. */}
      <section
        aria-label="Filters"
        className="flex flex-col gap-3.5 border-b pb-5 max-sm:hidden"
      >
        <SearchInput />
        {/* A search ranks by meaning alone; these don't apply to it. */}
        <div
          inert={!!filters.search}
          className={cn("flex flex-col gap-2", filters.search && "opacity-40")}
        >
          <FilterRow label="From">
            <FilterOptions
              label="From"
              options={ORIGIN_OPTIONS}
              value={filters.origin}
              onChange={(v) => setFilter("origin", v)}
            />
          </FilterRow>
          <FilterRow label="Topics">
            <FilterOptions
              label="Topics"
              options={TOPIC_OPTIONS}
              value={filters.topic}
              onChange={(v) => setFilter("topic", v)}
            />
          </FilterRow>
        </div>
      </section>
    </>
  )
}

/**
 * Phones don't get the filter rows, but a filter can still be active there:
 * one set before the window narrowed. Say what is
 * applied and offer a way out, or the wire looks inexplicably short.
 */
function MobileActiveFilters() {
  const { filters, setFilter } = useFilters()
  const { search, origin, topic } = filters

  // A search ignores the other filters, so name only the search.
  const applied = search
    ? [`"${search}"`]
    : [
        ORIGIN_OPTIONS.find((o) => o.value === origin && origin)?.label,
        findTopic(topic)?.label,
      ].filter(Boolean)

  if (applied.length === 0) return null

  return (
    <div className="mb-4 flex items-center gap-3 border-b pb-3 font-wire text-[11px] text-muted-foreground sm:hidden">
      <span className="min-w-0 truncate">
        Filtered by{" "}
        <span className="text-foreground">{applied.join(" · ")}</span>
      </span>
      <button
        type="button"
        onClick={() => {
          setFilter("search", "")
          setFilter("origin", "")
          setFilter("topic", "")
        }}
        className="ml-auto flex shrink-0 items-center gap-1 py-2 uppercase tracking-[0.08em] hover:text-foreground"
      >
        <X className="h-3 w-3" />
        Clear
      </button>
    </div>
  )
}

function SearchInput() {
  const { filters, setFilter } = useFilters()
  const [localSearch, setLocalSearch] = useState(filters.search)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null)

  function handleChange(v: string) {
    setLocalSearch(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setFilter("search", v), 300)
  }

  function handleClear() {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    setLocalSearch("")
    setFilter("search", "")
  }

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  // Clear from outside (the phone filter summary) has to empty the box too.
  useEffect(() => {
    if (filters.search === "") setLocalSearch("")
  }, [filters.search])

  return (
    <div className="flex items-center gap-2 border bg-background px-2.5 focus-within:border-foreground">
      <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <input
        type="text"
        aria-label="Search articles"
        placeholder="Search by meaning, e.g. run a model locally"
        value={localSearch}
        onChange={(e) => handleChange(e.target.value)}
        className="w-full min-w-0 bg-transparent py-2 text-[13px] outline-none placeholder:text-muted-foreground"
      />
      {localSearch && (
        <button
          type="button"
          aria-label="Clear search"
          onClick={handleClear}
          className="flex h-5 w-5 shrink-0 items-center justify-center text-muted-foreground hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  )
}
