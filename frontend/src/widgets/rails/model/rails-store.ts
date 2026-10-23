import { create } from "zustand"
import { trackEvent } from "@/shared/lib/analytics"
import {
  LEFT,
  type RailPanelDef,
  type RailPanels,
  RIGHT,
  type Side,
} from "../config/panels"
import { STORIES_PANEL_ID } from "../ui/panels/stories"

/**
 * wide: rails sit inline in the gutters beside the feed, always open.
 * narrow: both rails merge into one sheet behind one header button.
 */
type RailMode = "wide" | "narrow"
type ToggleVia = "key" | "button"

const WIDE_QUERY = "(min-width: 1360px)"
// Matches useIsMobile's breakpoint.
const PHONE_QUERY = "(max-width: 767px)"

function matches(query: string) {
  if (typeof window === "undefined" || !window.matchMedia) return false
  return window.matchMedia(query).matches
}

function readMode(): RailMode {
  if (typeof window === "undefined" || !window.matchMedia) return "wide"
  return matches(WIDE_QUERY) ? "wide" : "narrow"
}

// v2: panels start folded unless listed in OPEN_BY_DEFAULT, so v1's
// "collapsed" list no longer says enough.
const STORAGE_KEY = "agentique.rails.v2"

// Every other panel starts folded until the reader opens it.
const OPEN_BY_DEFAULT = new Set([STORIES_PANEL_ID])

type Open = Record<string, boolean>

// Storage can throw (private mode, blocked site data) or hold anything; the
// rails fall back to defaults rather than break the feed.
function load(): Open {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    const open: Open = {}
    if (parsed?.open && typeof parsed.open === "object") {
      for (const [id, v] of Object.entries(parsed.open)) {
        if (typeof v === "boolean") open[id] = v
      }
    }
    return open
  } catch {
    return {}
  }
}

function save(open: Open) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ open }))
  } catch {
    // Not remembered this time; the rails still work.
  }
}

type Overlay = Record<Side, boolean>
const CLOSED: Overlay = { left: false, right: false }

type RailsState = {
  mode: RailMode
  /** On a phone every panel is open and none folds. */
  phone: boolean
  /** Whether the current page shows rails at all. Set by `RailsLayout`. */
  present: boolean
  /** Stories is the one panel that can have nothing to show. Set by
   *  `RailsLayout`. */
  hasStories: boolean
  /** Below the wide breakpoint a rail is a temporary layer over the feed, so
   *  its open state is not remembered and starts closed on every load. On a
   *  wide screen there is room for both, so they are always open. */
  overlay: Overlay
  /** The reader's own open/fold choices, by panel id. */
  open: Open
}

export const useRails = create<RailsState>(() => ({
  mode: readMode(),
  phone: matches(PHONE_QUERY),
  present: false,
  hasStories: false,
  overlay: CLOSED,
  open: load(),
}))

if (typeof window !== "undefined" && window.matchMedia) {
  // Crossing a breakpoint drops any open overlay instead of carrying it into
  // a layout where it means something else.
  window
    .matchMedia(WIDE_QUERY)
    .addEventListener("change", () =>
      useRails.setState({ mode: readMode(), overlay: CLOSED }),
    )
  window
    .matchMedia(PHONE_QUERY)
    .addEventListener("change", () =>
      useRails.setState({ phone: matches(PHONE_QUERY) }),
    )
}

useRails.subscribe((state, prev) => {
  if (state.open !== prev.open) save(state.open)
})

// One object per combination, so a selector returns the same panels until
// the mode or Stories changes.
const arranged = new Map<string, RailPanels>()

/** A panel with nothing to show is left out, so a side whose panels are all
 *  empty renders no rail, strip or button. Below wide, both rails are one
 *  sheet behind one button: the right rail's panels follow the left's. */
export function selectPanels({ mode, hasStories }: RailsState): RailPanels {
  const key = `${mode}:${hasStories}`
  let panels = arranged.get(key)
  if (!panels) {
    const keep = (side: RailPanelDef[]) =>
      hasStories ? side : side.filter((p) => p.id !== STORIES_PANEL_ID)
    const left = keep(LEFT)
    const right = keep(RIGHT)
    panels =
      mode === "narrow"
        ? { left: [...left, ...right], right: [] }
        : { left, right }
    arranged.set(key, panels)
  }
  return panels
}

export function hasPanels(state: RailsState, side: Side) {
  return selectPanels(state)[side].length > 0
}

export function isOpen(state: RailsState, side: Side) {
  return state.mode === "wide" || state.overlay[side]
}

export function isCollapsed(state: RailsState, panelId: string) {
  return !state.phone && !(state.open[panelId] ?? OPEN_BY_DEFAULT.has(panelId))
}

// Whatever had focus when an overlay opened, to hand it back on close.
let returnFocus: HTMLElement | null = null

// Focus moves back once the rail has unmounted; until then it would land on
// an element about to disappear.
function restoreFocus() {
  const target = returnFocus
  returnFocus = null
  if (target?.isConnected) requestAnimationFrame(() => target.focus())
}

// One layer at a time: two overlays would cover most of a mid-size screen,
// and a sheet is full-screen anyway.
function setOverlay(side: Side, open: boolean) {
  useRails.setState({ overlay: open ? { ...CLOSED, [side]: true } : CLOSED })
}

export function toggleRail(side: Side, via: ToggleVia) {
  const state = useRails.getState()
  if (state.mode === "wide") return
  const open = !isOpen(state, side)
  if (open) {
    returnFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
  } else {
    restoreFocus()
  }
  setOverlay(side, open)
  trackEvent("rail_toggle", { side, open, via })
}

/** Close an overlay or sheet. `restore` sends focus back to whatever opened
 *  it; a click elsewhere on the page keeps focus where it landed. */
export function closeRail(side: Side, restore: boolean, via?: ToggleVia) {
  const state = useRails.getState()
  if (state.mode === "wide" || !isOpen(state, side)) return
  if (restore) restoreFocus()
  setOverlay(side, false)
  if (via) trackEvent("rail_toggle", { side, open: false, via })
}

export function togglePanel(panelId: string) {
  const state = useRails.getState()
  if (state.phone) return
  const open = isCollapsed(state, panelId)
  useRails.setState({ open: { ...state.open, [panelId]: open } })
  trackEvent("rail_panel_toggle", { panel: panelId, open })
}
