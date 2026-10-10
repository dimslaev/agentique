import type { ComponentType } from "react"

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
export const LEFT: RailPanelDef[] = []
export const RIGHT: RailPanelDef[] = []

export const RAIL_TITLES: Record<Side, string> = {
  left: "People and topics",
  right: "Stories",
}
