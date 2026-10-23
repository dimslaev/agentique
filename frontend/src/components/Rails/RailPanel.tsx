import { ChevronDown } from "lucide-react"
import { useId, useLayoutEffect, useRef, useState } from "react"
import { cn } from "@/shared/lib/utils"
import type { RailPanelDef } from "./panels"
import { useRails } from "./RailsProvider"

/** One collapsible section of a rail. Each folds on its own and is
 *  remembered across visits. On a phone all are open and none folds. */
export function RailPanel({ panel }: { panel: RailPanelDef }) {
  const { foldable, isCollapsed, togglePanel } = useRails()
  const bodyId = useId()
  const collapsed = isCollapsed(panel.id)
  const { Component } = panel
  const body = useRef<HTMLDivElement>(null)
  const [empty, setEmpty] = useState(false)

  // A panel with nothing to show renders null, and an open panel with an
  // empty body hides whole, header included. A folded one stays, since its
  // body is empty only because it is folded. Watched in JS rather than with
  // CSS :has(:empty), which Safari doesn't re-check when content arrives.
  useLayoutEffect(() => {
    const el = body.current
    if (!el || collapsed) {
      setEmpty(false)
      return
    }
    const check = () => setEmpty(el.childElementCount === 0)
    check()
    const observer = new MutationObserver(check)
    observer.observe(el, { childList: true })
    return () => observer.disconnect()
  }, [collapsed])

  return (
    <section className="border-b" data-panel={panel.id} hidden={empty}>
      {foldable ? (
        <button
          type="button"
          aria-expanded={!collapsed}
          aria-controls={bodyId}
          onClick={() => togglePanel(panel.id)}
          className="flex min-h-10 w-full items-center gap-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <PanelTitle title={panel.title} />
          <ChevronDown
            aria-hidden
            className={cn(
              "size-3 shrink-0 text-dim transition-transform ml-auto",
              collapsed && "-rotate-90",
            )}
          />
        </button>
      ) : (
        <h2 className="flex min-h-10 items-center">
          <PanelTitle title={panel.title} />
        </h2>
      )}
      <div ref={body} id={bodyId} hidden={collapsed} className="pb-[18px]">
        {!collapsed && <Component />}
      </div>
    </section>
  )
}

function PanelTitle({ title }: { title: string }) {
  return (
    <span className="font-wire text-[10px] font-semibold uppercase tracking-[0.1em]">
      {title}
    </span>
  )
}
