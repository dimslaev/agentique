import { useQuery } from "@tanstack/react-query"
import { Check, ChevronsUpDown } from "lucide-react"
import { useMemo, useState } from "react"
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
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { cn } from "@/lib/utils"
import { FilterOptionButton, FilterSectionLabel } from "./FilterOptionButton"

export type Facet = { slug: string; name: string; count?: number }

export function FacetFilter({
  label,
  value,
  topItems,
  selectedName,
  onChange,
  search,
}: {
  label: string
  /** selected slug, "" means no filter */
  value: string
  /** top-N facets to show as chips, e.g. from a /facets endpoint */
  topItems: Facet[]
  /** display name for `value` when it isn't in `topItems` (came from search) */
  selectedName?: string
  onChange: (slug: string, name?: string) => void
  search: (q: string) => Promise<Facet[]>
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const debouncedQuery = useDebouncedValue(query, 250)

  const { data: results, isFetching } = useQuery({
    queryKey: ["facet-search", label, debouncedQuery],
    queryFn: () => search(debouncedQuery),
    enabled: open,
    placeholderData: (prev) => prev,
  })

  // the selected item might not be in the top-N list (e.g. picked via search) —
  // inject it so it still renders as an active chip
  const items = useMemo(() => {
    if (!value || topItems.some((i) => i.slug === value)) return topItems
    return [{ slug: value, name: selectedName ?? value }, ...topItems]
  }, [topItems, value, selectedName])

  return (
    <div className="space-y-0.5">
      <FilterSectionLabel>{label}</FilterSectionLabel>
      <FilterOptionButton
        label="All"
        active={value === ""}
        onClick={() => onChange("", undefined)}
      />
      {items.map((item) => (
        <FilterOptionButton
          key={item.slug}
          label={item.name}
          active={item.slug === value}
          onClick={() => onChange(item.slug, item.name)}
        />
      ))}

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="flex shrink-0 items-center gap-1.5 rounded-sm px-2 py-[3px] text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronsUpDown className="h-3 w-3 shrink-0" />
            More…
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-56 p-0">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder={`Search ${label.toLowerCase()}…`}
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
                      onChange(item.slug, item.name)
                      setOpen(false)
                      setQuery("")
                    }}
                  >
                    <Check
                      className={cn(
                        "h-3.5 w-3.5",
                        item.slug === value ? "opacity-100" : "opacity-0",
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
    </div>
  )
}
