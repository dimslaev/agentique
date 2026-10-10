import type { ComponentType } from "react"
import { ReaderPicks } from "./panels/ReaderPicks"
import { TopicMap } from "./panels/TopicMap"
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
  {
    id: "topic-map",
    title: "Topic map",
    meta: "by meaning",
    Component: TopicMap,
  },
  {
    id: "reader-picks",
    title: "Reader picks",
    meta: "last 30 days",
    Component: ReaderPicks,
  },
]
export const RIGHT: RailPanelDef[] = []

export const RAIL_TITLES: Record<Side, string> = {
  left: "People and topics",
  right: "Stories",
}
