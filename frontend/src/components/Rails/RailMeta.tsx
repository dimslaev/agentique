import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/** A panel's small dim line under its heading, e.g. "Sep 29 – Oct 9 · 6".
 *  One style for every panel: date range first, then a count. */
export function RailMeta({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        "block font-wire text-[10px] tracking-[0.06em] text-dim tabular-nums",
        className,
      )}
    >
      {children}
    </span>
  )
}
