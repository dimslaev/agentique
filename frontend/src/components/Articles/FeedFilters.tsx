import { Search, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useFilters } from "@/context/filters"
import { cn } from "@/lib/utils"
import { FilterOptions, FilterRow } from "./FilterOption"
import { TOPICS } from "./topics"

// Who published it, or what it is when that is settled. Each article falls
// under exactly one: a repo is a repo whoever published it.
export const ORIGIN_OPTIONS = [
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
    <section
      aria-label="Filters"
      className="flex flex-col gap-3.5 border-b pb-5"
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

  return (
    <div className="flex items-center gap-2 border bg-background px-2.5 focus-within:border-foreground">
      <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <input
        type="text"
        aria-label="Search articles"
        placeholder="Search by meaning, e.g. run a model locally"
        value={localSearch}
        onChange={(e) => handleChange(e.target.value)}
        className="w-full min-w-0 bg-transparent py-2 text-base outline-none md:text-[13px] placeholder:text-muted-foreground"
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
