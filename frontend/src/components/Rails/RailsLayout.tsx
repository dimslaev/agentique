import { type ReactNode, useEffect, useRef } from "react"
import { PageColumn } from "@/components/Common/PageColumn"
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"
import type { Side } from "./panels"
import { Rail } from "./Rail"
import { RailStrip } from "./RailStrip"
import { useRails } from "./RailsProvider"

/**
 * The feed's page shell: the feed column with a rail on either side. The
 * column keeps the site's 768px width and never moves; rails live in the
 * gutters. With no panels registered this is exactly the plain column.
 */
export function RailsLayout({ children }: { children: ReactNode }) {
  const { mode, hasPanels, setPresent } = useRails()
  const left = hasPanels("left")
  const right = hasPanels("right")

  useEffect(() => {
    setPresent(true)
    return () => setPresent(false)
  }, [setPresent])

  if (!left && !right) return <PageColumn>{children}</PageColumn>

  // A 36px strip needs a gutter to sit in. Only on screens just past the
  // breakpoint does this take a few pixels from the feed column.
  const gutter = (has: boolean) =>
    mode === "mid" && has ? "minmax(52px,1fr)" : "minmax(0,1fr)"

  return (
    <>
      <div
        className="grid"
        style={{
          gridTemplateColumns: `${gutter(left)} minmax(0,768px) ${gutter(right)}`,
        }}
      >
        <RailSide side="left" />
        <div className="min-w-0 px-4">{children}</div>
        <RailSide side="right" />
      </div>
      {mode === "narrow" && left && <RailSheet side="left" />}
      {mode === "narrow" && right && <RailSheet side="right" />}
    </>
  )
}

function RailSide({ side }: { side: Side }) {
  const { mode, panels, isOpen } = useRails()
  const sidePanels = panels[side]
  if (mode === "narrow" || sidePanels.length === 0) return <div />

  const open = isOpen(side)
  return (
    <div
      className={cn(
        "flex min-w-0 items-start",
        side === "left" ? "justify-end" : "justify-start",
        side === "left"
          ? mode === "wide"
            ? "pr-7"
            : "pr-2"
          : mode === "wide"
            ? "pl-7"
            : "pl-2",
      )}
    >
      {mode === "wide" ? (
        <Rail
          side={side}
          panels={sidePanels}
          className="scrollbar-thin sticky top-[76px] max-h-[calc(100vh-92px)] w-full max-w-[272px] overflow-y-auto pb-10"
        />
      ) : (
        <RailStrip side={side} panels={sidePanels} />
      )}
      {mode === "mid" && open && <RailOverlay side={side} />}
    </div>
  )
}

/** Mid-size screens: the rail laid over the feed's edge. */
function RailOverlay({ side }: { side: Side }) {
  const { panels, close } = useRails()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      const target = e.target as Element | null
      if (ref.current?.contains(target)) return
      // Triggers toggle the rail themselves.
      if (target?.closest?.("[data-rail-trigger]")) return
      close(side, false)
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [side, close])

  return (
    <div
      ref={ref}
      className={cn(
        "scrollbar-thin fixed top-[60px] bottom-4 z-20 w-[300px] max-w-[calc(100vw-16px)] overflow-y-auto border bg-ink px-3.5 pb-6 shadow-[0_16px_48px_rgba(0,0,0,0.6)]",
        side === "left" ? "left-2" : "right-2",
      )}
    >
      <Rail side={side} panels={panels[side]} focusOnMount />
    </div>
  )
}

/** Phones: the rail as a full-screen sheet under the header. */
function RailSheet({ side }: { side: Side }) {
  const { panels, isOpen, close } = useRails()
  return (
    <Sheet
      open={isOpen(side)}
      onOpenChange={(open) => {
        if (!open) close(side, false)
      }}
      // Non-modal keeps the header live, so the button that opened the sheet
      // also closes it.
      modal={false}
    >
      <SheetContent
        side={side}
        aria-describedby={undefined}
        onOpenAutoFocus={(e) => e.preventDefault()}
        onCloseAutoFocus={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => {
          e.preventDefault()
          close(side, true, "key")
        }}
        onInteractOutside={(e) => {
          const target = e.detail.originalEvent.target as Element | null
          if (target?.closest?.("[data-rail-trigger]")) e.preventDefault()
        }}
        // No X: the header button that opened the sheet closes it.
        className="scrollbar-thin top-12! bottom-0 h-auto w-full gap-0 overflow-y-auto border-0 px-4 pb-4 shadow-none sm:max-w-none [&>button:last-child]:hidden"
      >
        {/* Radix needs a dialog title; there is no visible one. */}
        <SheetTitle className="sr-only">Rails</SheetTitle>
        <Rail side={side} panels={panels[side]} focusOnMount />
      </SheetContent>
    </Sheet>
  )
}
