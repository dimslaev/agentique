import { ChevronDown } from "lucide-react"
import { useId } from "react"
import { cn } from "@/lib/utils"
import type { RailPanelDef } from "./panels"
import { useRails } from "./RailsProvider"

/** One collapsible section of a rail. Each folds on its own and is
 *  remembered across visits. */
export function RailPanel({ panel }: { panel: RailPanelDef }) {
  const { isCollapsed, togglePanel } = useRails()
  const bodyId = useId()
  const collapsed = isCollapsed(panel.id)
  const { Component } = panel

  // A panel with nothing to show renders null, and an open panel with an
  // empty body hides whole, header included. A folded one stays, since its
  // body is empty only because it is folded.
  return (
    <section
      className="border-b [&:has(>div:not([hidden]):empty)]:hidden"
      data-panel={panel.id}
    >
      <button
        type="button"
        aria-expanded={!collapsed}
        aria-controls={bodyId}
        onClick={() => togglePanel(panel.id)}
        className="flex min-h-10 w-full items-center gap-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <span className="font-wire text-[10px] font-semibold uppercase tracking-[0.1em]">
          {panel.title}
        </span>
        {panel.meta && (
          <span className="ml-auto font-wire text-[10px] tracking-[0.06em] text-dim">
            {panel.meta}
          </span>
        )}
        <ChevronDown
          aria-hidden
          className={cn(
            "size-3 shrink-0 text-dim transition-transform",
            !panel.meta && "ml-auto",
            collapsed && "-rotate-90",
          )}
        />
      </button>
      <div id={bodyId} hidden={collapsed} className="pb-[18px]">
        {!collapsed && <Component />}
      </div>
    </section>
  )
}
