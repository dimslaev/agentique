import { type ReactNode, useEffect } from "react"
import { cn } from "@/shared/lib/utils"
import { PageColumn } from "@/shared/ui/page-column"
import { Sheet, SheetContent, SheetTitle } from "@/shared/ui/sheet"
import type { Side } from "../config/panels"
import {
  closeRail,
  hasPanels,
  isOpen,
  selectPanels,
  toggleRail,
  useRails,
} from "../model/rails-store"
import { useHasStories } from "./panels/stories"
import { Rail } from "./rail"

/**
 * The feed's page shell: the feed column with a rail on either side. The
 * column keeps the site's 768px width and never moves; on a wide screen the
 * rails live in the gutters, below it they are one sheet. With no panels
 * registered this is exactly the plain column.
 */
export function RailsLayout({ children }: { children: ReactNode }) {
  const mode = useRails((s) => s.mode)
  const left = useRails((s) => hasPanels(s, "left"))
  const right = useRails((s) => hasPanels(s, "right"))
  const hasStories = useHasStories()

  useEffect(() => {
    useRails.setState({ hasStories })
  }, [hasStories])

  useEffect(() => {
    useRails.setState({ present: true })
    document.addEventListener("keydown", onKey)
    return () => {
      useRails.setState({ present: false })
      document.removeEventListener("keydown", onKey)
    }
  }, [])

  if (!left && !right) return <PageColumn>{children}</PageColumn>

  if (mode === "narrow") {
    return (
      <>
        <PageColumn>{children}</PageColumn>
        <RailSheet side="left" />
      </>
    )
  }

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,768px)_minmax(0,1fr)]">
      <RailSide side="left" />
      <div className="min-w-0 px-4">{children}</div>
      <RailSide side="right" />
    </div>
  )
}

function RailSide({ side }: { side: Side }) {
  const panels = useRails(selectPanels)
  if (panels[side].length === 0) return <div />
  return (
    <div
      className={cn(
        "flex min-w-0 items-start",
        side === "left" ? "justify-end pr-7" : "justify-start pl-7",
      )}
    >
      <Rail
        side={side}
        panels={panels[side]}
        className="scrollbar-none fade-bottom sticky top-[76px] max-h-[calc(100vh-92px)] w-full max-w-[272px] overflow-y-auto pb-10"
      />
    </div>
  )
}

/** Below wide: the merged rail as a sheet under the header, full width on
 *  phones and a side panel on bigger screens. */
function RailSheet({ side }: { side: Side }) {
  const panels = useRails(selectPanels)
  const open = useRails((s) => isOpen(s, side))

  // The sheet is non-modal, so Radix leaves the page scrollable; lock it here
  // so a swipe on the sheet doesn't scroll the feed behind it.
  useEffect(() => {
    if (!open) return
    const html = document.documentElement
    const prev = html.style.overflow
    html.style.overflow = "hidden"
    return () => {
      html.style.overflow = prev
    }
  }, [open])

  return (
    <Sheet
      open={open}
      onOpenChange={(open) => {
        if (!open) closeRail(side, false)
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
          closeRail(side, true, "key")
        }}
        onInteractOutside={(e) => {
          const target = e.detail.originalEvent.target as Element | null
          if (target?.closest?.("[data-rail-trigger]")) e.preventDefault()
        }}
        // No X: the header button that opened the sheet closes it.
        className="scrollbar-none top-12! bottom-0 h-auto w-full gap-0 overflow-y-auto border-0 px-4 pb-4 shadow-none sm:max-w-[360px] sm:border-r [&>button:last-child]:hidden"
      >
        {/* Radix needs a dialog title; there is no visible one. */}
        <SheetTitle className="sr-only">Rails</SheetTitle>
        <Rail side={side} panels={panels[side]} focusOnMount />
      </SheetContent>
    </Sheet>
  )
}

// [ and ] toggle a side's rail below wide, Escape closes it. Keys typed into a
// field, or held with a modifier, are the reader's, not the rails'.
function onKey(e: KeyboardEvent) {
  if (e.defaultPrevented || e.isComposing) return
  if (e.metaKey || e.ctrlKey || e.altKey) return
  if (isTyping(e.target)) return
  const state = useRails.getState()
  const side: Side | null =
    e.key === "[" ? "left" : e.key === "]" ? "right" : null
  if (side && hasPanels(state, side) && state.mode !== "wide") {
    e.preventDefault()
    toggleRail(side, "key")
  } else if (e.key === "Escape" && state.mode !== "wide") {
    for (const s of ["left", "right"] as const) closeRail(s, true, "key")
  }
}

function isTyping(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  )
}
