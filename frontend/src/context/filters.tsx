import { createContext, type ReactNode, useContext, useState } from "react"

export type Filters = {
  search: string
  dateRange: string
  sort: string
  category: string
  kind: string
  tag: string
  /** Display name for `tag`, which may not be among the top facets when it
   *  came from a row or from search. Not sent to the API. */
  tagName: string
}

type FiltersContextType = {
  filters: Filters
  setFilter: (key: keyof Filters, value: string) => void
  setTag: (slug: string, name: string) => void
}

const FiltersContext = createContext<FiltersContextType | null>(null)

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<Filters>({
    search: "",
    dateRange: "1w",
    sort: "published_at-desc",
    category: "",
    kind: "",
    tag: "",
    tagName: "",
  })

  const setFilter = (key: keyof Filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const setTag = (slug: string, name: string) => {
    setFilters((prev) => ({ ...prev, tag: slug, tagName: name }))
  }

  return (
    <FiltersContext.Provider value={{ filters, setFilter, setTag }}>
      {children}
    </FiltersContext.Provider>
  )
}

export function useFilters() {
  const ctx = useContext(FiltersContext)
  if (!ctx) throw new Error("useFilters must be used within FiltersProvider")
  return ctx
}
