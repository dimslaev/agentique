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
import { trackEvent } from "@/shared/lib/analytics"
import {
  LEFT,
  type RailPanelDef,
  type RailPanels,
  RIGHT,
  type Side,
} from "./panels"
import { STORIES_PANEL_ID, useHasStories } from "./panels/Stories"

/**
 * wide: rails sit inline in the gutters beside the feed, always open.
 * narrow: both rails merge into one sheet behind one header button.
 */
export type RailMode = "wide" | "narrow"
export type ToggleVia = "key" | "button"

const WIDE_QUERY = "(min-width: 1360px)"
// Matches useIsMobile's breakpoint.
const PHONE_QUERY = "(max-width: 767px)"

function matches(query: string) {
  if (typeof window === "undefined" || !window.matchMedia) return false
  return window.matchMedia(query).matches
}

function subscribeTo(query: string) {
  return (onChange: () => void) => {
    if (typeof window === "undefined" || !window.matchMedia) return () => {}
    const mql = window.matchMedia(query)
    mql.addEventListener("change", onChange)
    return () => mql.removeEventListener("change", onChange)
  }
}

function readMode(): RailMode {
  if (typeof window === "undefined" || !window.matchMedia) return "wide"
  return matches(WIDE_QUERY) ? "wide" : "narrow"
}

const subscribeMode = subscribeTo(WIDE_QUERY)
const subscribePhone = subscribeTo(PHONE_QUERY)
const readPhone = () => matches(PHONE_QUERY)

// v2: panels start folded unless listed in OPEN_BY_DEFAULT, so v1's
// "collapsed" list no longer says enough.
const STORAGE_KEY = "agentique.rails.v2"

// Every other panel starts folded until the reader opens it.
const OPEN_BY_DEFAULT = new Set([STORIES_PANEL_ID])

type Stored = {
  /** The reader's own open/fold choices, by panel id. */
  open: Record<string, boolean>
}

const DEFAULTS: Stored = { open: {} }

// Storage can throw (private mode, blocked site data) or hold anything; the
// rails fall back to defaults rather than break the feed.
function load(): Stored {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULTS
    const parsed = JSON.parse(raw)
    const open: Record<string, boolean> = {}
    if (parsed?.open && typeof parsed.open === "object") {
      for (const [id, v] of Object.entries(parsed.open)) {
        if (typeof v === "boolean") open[id] = v
      }
    }
    return { open }
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
  /** On a phone every panel is open and none folds. */
  foldable: boolean
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
  const mode = useSyncExternalStore<RailMode>(
    subscribeMode,
    readMode,
    () => "wide",
  )
  const phone = useSyncExternalStore(subscribePhone, readPhone, () => false)
  // Below wide, both rails are one sheet behind one button: the right rail's
  // panels follow the left's.
  const panels = useMemo(() => {
    // Stories can be registered on either side; with nothing to show it is
    // left out so its side can go empty and lose its rail and button.
    const keep = (side: RailPanelDef[]) =>
      hasStories ? side : side.filter((p) => p.id !== STORIES_PANEL_ID)
    const left = keep(registered.left)
    const right = keep(registered.right)
    return mode === "narrow"
      ? { left: [...left, ...right], right: [] }
      : { left, right }
  }, [registered, hasStories, mode])
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

  const isCollapsed = useCallback(
    (panelId: string) =>
      !phone && !(stored.open[panelId] ?? OPEN_BY_DEFAULT.has(panelId)),
    [phone, stored],
  )

  const togglePanel = useCallback(
    (panelId: string) => {
      if (phone) return
      const open = isCollapsed(panelId)
      setStored((s) => ({ ...s, open: { ...s.open, [panelId]: open } }))
      trackEvent("rail_panel_toggle", { panel: panelId, open })
    },
    [phone, isCollapsed],
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
      foldable: !phone,
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
      phone,
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
