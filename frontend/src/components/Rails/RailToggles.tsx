import { PanelLeft, PanelRight } from "lucide-react"
import type { Side } from "./panels"
import { useRails } from "./RailsProvider"

const SIDES: Side[] = ["left", "right"]
const KEYS: Record<Side, string> = { left: "[", right: "]" }

/** Header buttons for the page's rails, below the wide breakpoint only: on a
 *  wide screen the rails are always open. Nothing on a page without rails,
 *  and nothing for a side with no panels. Phones get one button, as their
 *  rails are merged into one sheet. */
export function RailToggles() {
  const { mode, present, hasPanels, isOpen, toggle } = useRails()
  if (!present || mode === "wide") return null
  return (
    <>
      {SIDES.filter(hasPanels).map((side) => {
        const Icon = side === "left" ? PanelLeft : PanelRight
        const label =
          mode === "narrow"
            ? "Rails"
            : side === "left"
              ? "Left rail"
              : "Right rail"
        return (
          <button
            key={side}
            type="button"
            data-rail-trigger
            aria-pressed={isOpen(side)}
            aria-label={`Toggle the ${label.toLowerCase()}`}
            title={`${label} (${KEYS[side]})`}
            onClick={() => toggle(side, "button")}
            className="flex size-8 items-center justify-center text-dim transition-colors hover:text-foreground aria-pressed:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <Icon className="size-[18px]" aria-hidden />
          </button>
        )
      })}
    </>
  )
}
