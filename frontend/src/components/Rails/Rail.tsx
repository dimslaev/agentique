import { ChevronsLeft, ChevronsRight } from "lucide-react"
import { useEffect, useRef } from "react"
import { SheetTitle } from "@/components/ui/sheet"
import { RAIL_TITLES, type RailPanelDef, type Side } from "./panels"
import { RailPanel } from "./RailPanel"
import { useRails } from "./RailsProvider"

/** A rail: a heading row with a hide button, then its panels. The same
 *  markup sits inline, over the feed's edge, or in a phone sheet. */
export function Rail({
  side,
  panels,
  focusOnMount = false,
  inSheet = false,
  hideable = true,
  className,
}: {
  side: Side
  panels: RailPanelDef[]
  /** Overlay and sheet move focus to the heading as they open. */
  focusOnMount?: boolean
  /** A sheet's heading doubles as its dialog title. */
  inSheet?: boolean
  /** Inline rails on a wide screen are always open, so have no hide button. */
  hideable?: boolean
  className?: string
}) {
  const { toggle } = useRails()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const title = RAIL_TITLES[side]
  const Hide = side === "left" ? ChevronsLeft : ChevronsRight

  useEffect(() => {
    if (focusOnMount) headingRef.current?.focus()
  }, [focusOnMount])

  const heading = (
    <h2
      ref={headingRef}
      tabIndex={-1}
      className="font-display text-sm font-bold uppercase tracking-[0.1em] outline-none"
    >
      {title}
    </h2>
  )

  return (
    <aside aria-label={title} data-rail={side} className={className}>
      <div className="flex items-center justify-between gap-2 border-b py-[9px]">
        {inSheet ? <SheetTitle asChild>{heading}</SheetTitle> : heading}
        {hideable && (
          <button
            type="button"
            aria-label={`Hide the ${title.toLowerCase()} rail`}
            onClick={() => toggle(side, "button")}
            className="flex size-8 items-center justify-center text-dim transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <Hide className="size-3.5" aria-hidden />
          </button>
        )}
      </div>
      {panels.map((panel) => (
        <RailPanel key={panel.id} panel={panel} />
      ))}
    </aside>
  )
}
