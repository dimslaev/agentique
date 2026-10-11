import { createContext, type ReactNode, useContext, useState } from "react"

export type Filters = {
  search: string
  dateRange: string
  sort: string
  /** The "From" row: who published it, or what it is. */
  origin: string
  /** A slug from `TOPICS`. */
  topic: string
  /** A publisher slug, set from the Voices panel. */
  publisher: string
  /** That publisher's name, for the chip that clears it. */
  publisherName: string
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
    origin: "",
    topic: "",
    publisher: "",
    publisherName: "",
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
