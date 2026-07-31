import { useQuery } from "@tanstack/react-query"
import { Search, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { ArticlesService } from "@/client"
import { useFilters } from "@/context/filters"
import { FacetFilter } from "./FacetFilter"
import { FilterOptionButton, FilterSectionLabel } from "./FilterOptionButton"

const DATE_OPTIONS = [
  { value: "3d", label: "Last 3 days" },
  { value: "1w", label: "Last week" },
  { value: "1m", label: "Last month" },
]

const SORT_OPTIONS = [
  { value: "published_at-desc", label: "Date" },
  { value: "score-desc", label: "Score" },
  { value: "likes-desc", label: "Popular" },
]

const CATEGORY_OPTIONS = [
  { value: "", label: "All" },
  { value: "models", label: "Models" },
  { value: "dev", label: "Dev" },
  { value: "research", label: "Research" },
]

const KIND_OPTIONS = [
  { value: "", label: "All" },
  { value: "repo", label: "Repo" },
  { value: "paper", label: "Paper" },
  { value: "model", label: "Model" },
  { value: "blog", label: "Blog" },
  { value: "product", label: "Product" },
  { value: "announcement", label: "Announcement" },
]

function FilterGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { value: string; label: string }[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="space-y-0.5">
      <FilterSectionLabel>{label}</FilterSectionLabel>
      {options.map((o) => (
        <FilterOptionButton
          key={o.value}
          label={o.label}
          active={o.value === value}
          onClick={() => onChange(o.value)}
        />
      ))}
    </div>
  )
}

export function SidebarFilters() {
  const { filters, setFilter } = useFilters()
  const [localSearch, setLocalSearch] = useState(filters.search)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null)
  // names for the current publisher/tag slug when it came from search and
  // isn't among the top facets — kept out of context since it's display-only
  const [publisherName, setPublisherName] = useState<string>()
  const [tagName, setTagName] = useState<string>()

  const { data: facets } = useQuery({
    queryKey: ["article-facets"],
    queryFn: () => ArticlesService.articleFacets(),
    staleTime: 5 * 60 * 1000,
  })

  function handleSearchChange(v: string) {
    setLocalSearch(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setFilter("search", v), 300)
  }

  function handleSearchClear() {
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
    <div className="flex flex-col gap-4">
      <div className="relative flex items-center rounded-sm border bg-background px-2">
        <Search className="h-3 w-3 shrink-0 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search…"
          value={localSearch}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="w-full bg-transparent py-1.5 pl-2 text-xs outline-none placeholder:text-muted-foreground"
        />
        {localSearch && (
          <button
            type="button"
            onClick={handleSearchClear}
            className="flex h-4 w-4 shrink-0 items-center justify-center text-muted-foreground hover:text-foreground"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>

      <FilterGroup
        label="Published"
        options={DATE_OPTIONS}
        value={filters.dateRange}
        onChange={(v) => setFilter("dateRange", v)}
      />
      <FilterGroup
        label="Sort by"
        options={SORT_OPTIONS}
        value={filters.sort}
        onChange={(v) => setFilter("sort", v)}
      />
      <FilterGroup
        label="Category"
        options={CATEGORY_OPTIONS}
        value={filters.category}
        onChange={(v) => setFilter("category", v)}
      />
      <FilterGroup
        label="Kind"
        options={KIND_OPTIONS}
        value={filters.kind}
        onChange={(v) => setFilter("kind", v)}
      />
      <FacetFilter
        label="Publisher"
        value={filters.publisher}
        selectedName={publisherName}
        topItems={facets?.publishers ?? []}
        onChange={(slug, name) => {
          setFilter("publisher", slug)
          setPublisherName(name)
        }}
        search={(q) => ArticlesService.searchPublishers({ q, limit: 20 })}
      />
      <FacetFilter
        label="Tags"
        value={filters.tag}
        selectedName={tagName}
        topItems={facets?.tags ?? []}
        onChange={(slug, name) => {
          setFilter("tag", slug)
          setTagName(name)
        }}
        search={(q) => ArticlesService.searchTags({ q, limit: 20 })}
      />
    </div>
  )
}
