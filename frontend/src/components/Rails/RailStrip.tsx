import { cn } from "@/lib/utils"
import type { RailPanelDef, Side } from "./panels"
import { useRails } from "./RailsProvider"

/** A closed rail: a 36px strip with one vertical label per panel. A label
 *  opens the rail with that panel expanded. */
export function RailStrip({
  side,
  panels,
  fresh,
}: {
  side: Side
  panels: RailPanelDef[]
  /** Panel ids with something new inside; each gets an orange dot. */
  fresh?: string[]
}) {
  const { openPanel } = useRails()
  return (
    <nav
      aria-label={`${side === "left" ? "Left" : "Right"} rail, collapsed`}
      className="sticky top-[76px] flex w-9 flex-col items-center gap-0.5 border py-1"
    >
      {panels.map((panel) => {
        const isFresh = fresh?.includes(panel.id)
        return (
          <button
            key={panel.id}
            type="button"
            data-rail-trigger
            onClick={() => openPanel(side, panel.id)}
            className={cn(
              "flex items-center gap-2 py-3 font-wire text-[10px] uppercase tracking-[0.12em] text-dim [writing-mode:vertical-rl] hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
              // Left-side labels read bottom to top, so both strips' text
              // faces the feed.
              side === "left" && "rotate-180",
            )}
          >
            {isFresh && (
              <span aria-hidden className="size-1.5 shrink-0 bg-primary" />
            )}
            {panel.title}
            {isFresh && <span className="sr-only">, new</span>}
          </button>
        )
      })}
    </nav>
  )
}
