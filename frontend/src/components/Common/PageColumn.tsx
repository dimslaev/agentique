import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

// The site's reading column. The header and footer use the same width, so a
// page inside it lines up with both.
export function PageColumn({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("mx-auto w-full max-w-3xl px-4", className)}>
      {children}
    </div>
  )
}
