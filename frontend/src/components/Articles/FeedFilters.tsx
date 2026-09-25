import { useQuery } from "@tanstack/react-query"
import { Check, ChevronsUpDown, Search, X } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { ArticlesService } from "@/client"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { useFilters } from "@/context/filters"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { cn } from "@/lib/utils"
import { FilterOptions, FilterRow } from "./FilterOption"

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

// Enough to show the busiest tags on one line at desktop width; the rest are
// behind "More…".
const TOP_TAGS = 4

export function FeedFilters() {
  const { filters, setFilter } = useFilters()

  return (
    <section
      aria-label="Filters"
      className="flex flex-col gap-3.5 border-b pb-5"
    >
      <SearchInput />
      <div className="flex flex-col gap-2">
        <FilterRow label="Category">
          <FilterOptions
            label="Category"
            options={CATEGORY_OPTIONS}
            value={filters.category}
            onChange={(v) => setFilter("category", v)}
          />
        </FilterRow>
        <FilterRow label="Kind">
          <FilterOptions
            label="Kind"
            options={KIND_OPTIONS}
            value={filters.kind}
            onChange={(v) => setFilter("kind", v)}
          />
        </FilterRow>
        <FilterRow label="Tags">
          <TagOptions />
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

function TagOptions() {
  const { filters, setTag } = useFilters()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const debouncedQuery = useDebouncedValue(query, 250)

  const { data: facets } = useQuery({
    queryKey: ["article-facets", TOP_TAGS],
    queryFn: () => ArticlesService.articleFacets({ limit: TOP_TAGS }),
    staleTime: 5 * 60 * 1000,
  })

  const { data: results, isFetching } = useQuery({
    queryKey: ["facet-search", "tags", debouncedQuery],
    queryFn: () => ArticlesService.searchTags({ q: debouncedQuery, limit: 20 }),
    enabled: open,
    placeholderData: (prev) => prev,
  })

  // The selected tag may have come from a row or from search rather than the
  // top facets; show it anyway so the active filter is always visible.
  const options = useMemo(() => {
    const top = (facets?.tags ?? []).map((t) => ({
      value: t.slug,
      label: t.name,
    }))
    const selected = filters.tag
    const extra =
      selected && !top.some((t) => t.value === selected)
        ? [{ value: selected, label: filters.tagName || selected }]
        : []
    return [{ value: "", label: "All" }, ...extra, ...top]
  }, [facets, filters.tag, filters.tagName])

  return (
    <FilterOptions
      label="Tags"
      options={options}
      value={filters.tag}
      onChange={(slug) =>
        setTag(slug, options.find((o) => o.value === slug)?.label ?? "")
      }
    >
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="flex items-center gap-1 whitespace-nowrap px-1.5 py-1 text-[13px] leading-4 text-muted-foreground transition-colors hover:text-foreground max-sm:px-2 max-sm:py-2"
          >
            <ChevronsUpDown className="h-3 w-3 shrink-0" />
            More…
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-56 p-0">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder="Search tags…"
              value={query}
              onValueChange={setQuery}
            />
            <CommandList>
              <CommandEmpty>
                {isFetching ? "Searching…" : "No results."}
              </CommandEmpty>
              <CommandGroup>
                {(results ?? []).map((item) => (
                  <CommandItem
                    key={item.slug}
                    value={item.slug}
                    onSelect={() => {
                      setTag(item.slug, item.name)
                      setOpen(false)
                      setQuery("")
                    }}
                  >
                    <Check
                      className={cn(
                        "h-3.5 w-3.5",
                        item.slug === filters.tag ? "opacity-100" : "opacity-0",
                      )}
                    />
                    {item.name}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </FilterOptions>
  )
}
