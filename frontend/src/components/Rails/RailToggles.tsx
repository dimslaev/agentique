import { PanelLeft, PanelRight } from "lucide-react"
import { RAIL_TITLES, type Side } from "./panels"
import { useRails } from "./RailsProvider"

const SIDES: Side[] = ["left", "right"]
const KEYS: Record<Side, string> = { left: "[", right: "]" }

/** Header buttons for the page's rails. Nothing on a page without rails, and
 *  nothing for a side with no panels. */
export function RailToggles() {
  const { present, hasPanels, isOpen, toggle } = useRails()
  if (!present) return null
  return (
    <>
      {SIDES.filter(hasPanels).map((side) => {
        const Icon = side === "left" ? PanelLeft : PanelRight
        const title = RAIL_TITLES[side]
        return (
          <button
            key={side}
            type="button"
            data-rail-trigger
            aria-pressed={isOpen(side)}
            aria-label={`Toggle the ${title.toLowerCase()} rail`}
            title={`${title} (${KEYS[side]})`}
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
