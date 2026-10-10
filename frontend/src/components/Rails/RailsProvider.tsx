import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react"
import { trackEvent } from "@/lib/analytics"
import { LEFT, type RailPanels, RIGHT, type Side } from "./panels"
import { STORIES_PANEL_ID, useHasStories } from "./panels/Stories"

/**
 * wide: rails sit inline in the gutters beside the feed, always open.
 * mid: rails fold to edge strips and open over the feed's edge.
 * narrow: no strips; header buttons open a rail as a full-screen sheet.
 */
export type RailMode = "wide" | "mid" | "narrow"
export type ToggleVia = "key" | "button" | "strip"

const WIDE_QUERY = "(min-width: 1360px)"
const MID_QUERY = "(min-width: 760px)"

function readMode(): RailMode {
  if (typeof window === "undefined" || !window.matchMedia) return "wide"
  if (window.matchMedia(WIDE_QUERY).matches) return "wide"
  if (window.matchMedia(MID_QUERY).matches) return "mid"
  return "narrow"
}

function subscribeMode(onChange: () => void) {
  if (typeof window === "undefined" || !window.matchMedia) return () => {}
  const queries = [WIDE_QUERY, MID_QUERY].map((q) => window.matchMedia(q))
  for (const q of queries) q.addEventListener("change", onChange)
  return () => {
    for (const q of queries) q.removeEventListener("change", onChange)
  }
}

const STORAGE_KEY = "agentique.rails.v1"

type Stored = {
  collapsed: Record<string, true>
}

const DEFAULTS: Stored = { collapsed: {} }

// Storage can throw (private mode, blocked site data) or hold anything; the
// rails fall back to defaults rather than break the feed.
function load(): Stored {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULTS
    const parsed = JSON.parse(raw)
    const collapsed: Record<string, true> = {}
    if (parsed?.collapsed && typeof parsed.collapsed === "object") {
      for (const [id, v] of Object.entries(parsed.collapsed)) {
        if (v === true) collapsed[id] = true
      }
    }
    return { collapsed }
  } catch {
    return DEFAULTS
  }
}

function save(stored: Stored) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
  } catch {
    // Not remembered this time; the rails still work.
  }
}

type Overlay = Record<Side, boolean>
const CLOSED: Overlay = { left: false, right: false }

type RailsContextType = {
  mode: RailMode
  panels: RailPanels
  /** Whether the current page shows rails at all. Set by `RailsLayout`. */
  present: boolean
  setPresent: (present: boolean) => void
  isOpen: (side: Side) => boolean
  hasPanels: (side: Side) => boolean
  toggle: (side: Side, via: ToggleVia) => void
  /** Close an overlay or sheet. `restoreFocus` sends focus back to whatever
   *  opened it; a click elsewhere on the page keeps focus where it landed. */
  close: (side: Side, restoreFocus: boolean, via?: ToggleVia) => void
  /** A strip label: open the rail with that panel expanded. */
  openPanel: (side: Side, panelId: string) => void
  isCollapsed: (panelId: string) => boolean
  togglePanel: (panelId: string) => void
}

const RailsContext = createContext<RailsContextType | null>(null)

const REGISTERED: RailPanels = { left: LEFT, right: RIGHT }

export function RailsProvider({
  children,
  panels: registered = REGISTERED,
}: {
  children: ReactNode
  panels?: RailPanels
}) {
  // A panel with nothing to show is left out, so a side whose panels are all
  // empty renders no rail, strip or button. Stories is the one that can be.
  const hasStories = useHasStories()
  const panels = useMemo(
    () =>
      hasStories
        ? registered
        : {
            ...registered,
            right: registered.right.filter((p) => p.id !== STORIES_PANEL_ID),
          },
    [registered, hasStories],
  )
  const mode = useSyncExternalStore<RailMode>(
    subscribeMode,
    readMode,
    () => "wide",
  )
  const [stored, setStored] = useState<Stored>(load)
  // Below the wide breakpoint a rail is a temporary layer over the feed, so
  // its open state is not remembered and starts closed on every load. On a
  // wide screen there is room for both, so they are always open.
  const [overlay, setOverlay] = useState<Overlay>(CLOSED)
  const [present, setPresent] = useState(false)
  const returnFocus = useRef<HTMLElement | null>(null)

  useEffect(() => {
    save(stored)
  }, [stored])

  // Crossing a breakpoint drops any open overlay instead of carrying it into
  // a layout where it means something else.
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset on mode change only
  useEffect(() => {
    setOverlay(CLOSED)
  }, [mode])

  const hasPanels = useCallback(
    (side: Side) => panels[side].length > 0,
    [panels],
  )

  const isOpen = useCallback(
    (side: Side) => mode === "wide" || overlay[side],
    [mode, overlay],
  )

  const setOpen = useCallback((side: Side, open: boolean) => {
    // One layer at a time: two overlays would cover most of a mid-size
    // screen, and a sheet is full-screen anyway.
    setOverlay(open ? { ...CLOSED, [side]: true } : CLOSED)
  }, [])

  // Focus moves back once the rail has unmounted; until then it would land
  // on an element about to disappear.
  const restore = useCallback(() => {
    const target = returnFocus.current
    returnFocus.current = null
    if (target?.isConnected) requestAnimationFrame(() => target.focus())
  }, [])

  const toggle = useCallback(
    (side: Side, via: ToggleVia) => {
      if (mode === "wide") return
      const open = !isOpen(side)
      if (open) {
        returnFocus.current =
          document.activeElement instanceof HTMLElement
            ? document.activeElement
            : null
      } else {
        restore()
      }
      setOpen(side, open)
      trackEvent("rail_toggle", { side, open, via })
    },
    [isOpen, mode, setOpen, restore],
  )

  const close = useCallback(
    (side: Side, restoreFocus: boolean, via?: ToggleVia) => {
      if (mode === "wide" || !isOpen(side)) return
      if (restoreFocus) restore()
      setOpen(side, false)
      if (via) trackEvent("rail_toggle", { side, open: false, via })
    },
    [mode, isOpen, setOpen, restore],
  )

  const togglePanel = useCallback(
    (panelId: string) => {
      const open = stored.collapsed[panelId] === true
      setStored((s) => {
        const collapsed = { ...s.collapsed }
        if (open) delete collapsed[panelId]
        else collapsed[panelId] = true
        return { ...s, collapsed }
      })
      trackEvent("rail_panel_toggle", { panel: panelId, open })
    },
    [stored],
  )

  const isCollapsed = useCallback(
    (panelId: string) => stored.collapsed[panelId] === true,
    [stored],
  )

  const openPanel = useCallback(
    (side: Side, panelId: string) => {
      if (isCollapsed(panelId)) togglePanel(panelId)
      if (!isOpen(side)) toggle(side, "strip")
    },
    [isCollapsed, isOpen, toggle, togglePanel],
  )

  useEffect(() => {
    if (!present) return
    function onKey(e: KeyboardEvent) {
      if (e.defaultPrevented || e.isComposing) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTyping(e.target)) return
      const side: Side | null =
        e.key === "[" ? "left" : e.key === "]" ? "right" : null
      if (side && hasPanels(side) && mode !== "wide") {
        e.preventDefault()
        toggle(side, "key")
      } else if (e.key === "Escape" && mode !== "wide") {
        for (const s of ["left", "right"] as const) close(s, true, "key")
      }
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [present, hasPanels, toggle, close, mode])

  const value = useMemo(
    () => ({
      mode,
      panels,
      present,
      setPresent,
      isOpen,
      hasPanels,
      toggle,
      close,
      openPanel,
      isCollapsed,
      togglePanel,
    }),
    [
      mode,
      panels,
      present,
      isOpen,
      hasPanels,
      toggle,
      close,
      openPanel,
      isCollapsed,
      togglePanel,
    ],
  )

  return <RailsContext.Provider value={value}>{children}</RailsContext.Provider>
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

export function useRails() {
  const ctx = useContext(RailsContext)
  if (!ctx) throw new Error("useRails must be used within RailsProvider")
  return ctx
}
