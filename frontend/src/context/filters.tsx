import { createContext, type ReactNode, useContext, useState } from "react"

export type Filters = {
  search: string
  dateRange: string
  sort: string
  /** Category slug from the server vocabulary. Replaces the old free-text
   *  dev/models/research enum and the separate tag filter. */
  category: string
  kind: string
  publisher: string
}

type FiltersContextType = {
  filters: Filters
  setFilter: (key: keyof Filters, value: string) => void
}

const FiltersContext = createContext<FiltersContextType | null>(null)

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<Filters>({
    search: "",
    dateRange: "1w",
    sort: "published_at-desc",
    category: "",
    kind: "",
    publisher: "",
  })

  const setFilter = (key: keyof Filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <FiltersContext.Provider value={{ filters, setFilter }}>
      {children}
    </FiltersContext.Provider>
  )
}

export function useFilters() {
  const ctx = useContext(FiltersContext)
  if (!ctx) throw new Error("useFilters must be used within FiltersProvider")
  return ctx
}
