import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"
import type { RailPanelDef, Side } from "./panels"
import { RailPanel } from "./RailPanel"

/** A rail: its panels, nothing above them. The same markup sits inline,
 *  over the feed's edge, or in a phone sheet. */
export function Rail({
  side,
  panels,
  focusOnMount = false,
  className,
}: {
  side: Side
  panels: RailPanelDef[]
  /** Overlay and sheet move focus to the rail as they open. */
  focusOnMount?: boolean
  className?: string
}) {
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    if (focusOnMount) ref.current?.focus()
  }, [focusOnMount])

  return (
    <aside
      ref={ref}
      tabIndex={-1}
      aria-label={side === "left" ? "Left rail" : "Right rail"}
      data-rail={side}
      className={cn("outline-none", className)}
    >
      {panels.map((panel) => (
        <RailPanel key={panel.id} panel={panel} />
      ))}
    </aside>
  )
}
