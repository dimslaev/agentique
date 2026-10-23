import { PanelLeft, PanelRight } from "lucide-react"
import type { Side } from "../config/panels"
import { selectPanels, toggleRail, useRails } from "../model/rails-store"

const SIDES: Side[] = ["left", "right"]
const KEYS: Record<Side, string> = { left: "[", right: "]" }

/** Header buttons for the page's rails, below the wide breakpoint only: on a
 *  wide screen the rails are always open. Nothing on a page without rails,
 *  and nothing for a side with no panels. Below wide the rails are merged
 *  into one sheet, so there is one button. */
export function RailToggles() {
  const mode = useRails((s) => s.mode)
  const present = useRails((s) => s.present)
  const overlay = useRails((s) => s.overlay)
  const panels = useRails(selectPanels)
  if (!present || mode === "wide") return null
  return (
    <>
      {SIDES.filter((side) => panels[side].length > 0).map((side) => {
        const Icon = side === "left" ? PanelLeft : PanelRight
        const label = "Rails"
        return (
          <button
            key={side}
            type="button"
            data-rail-trigger
            aria-pressed={overlay[side]}
            aria-label={`Toggle the ${label.toLowerCase()}`}
            title={`${label} (${KEYS[side]})`}
            onClick={() => toggleRail(side, "button")}
            className="flex size-8 items-center justify-center text-dim transition-colors hover:text-foreground aria-pressed:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <Icon className="size-[18px]" aria-hidden />
          </button>
        )
      })}
    </>
  )
}
