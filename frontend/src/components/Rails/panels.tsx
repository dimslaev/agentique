import type { ComponentType } from "react"
import { STORIES_PANEL_ID, Stories } from "./panels/Stories"
import { WhoWrote } from "./panels/WhoWrote"

export type Side = "left" | "right"

export type RailPanelDef = {
  /** Stable key: persisted in localStorage and sent with analytics. */
  id: string
  title: string
  /** Short dim note on the right of the panel header, e.g. "since Sep 7". */
  meta?: string
  Component: ComponentType
}

export type RailPanels = Record<Side, RailPanelDef[]>

// Planned: left = "Who wrote this week", "Topic map"; right = "Stories".
// A side with no panels renders nothing at all: no rail, strip or button.
export const LEFT: RailPanelDef[] = [
  { id: "who-wrote", title: "Who wrote the wire", Component: WhoWrote },
]
export const RIGHT: RailPanelDef[] = [
  {
    id: STORIES_PANEL_ID,
    title: "Stories",
    meta: "named by the agent",
    Component: Stories,
  },
]

export const RAIL_TITLES: Record<Side, string> = {
  left: "People and topics",
  right: "Stories",
}
