import type { ComponentType } from "react"
import { ReaderPicks } from "./panels/ReaderPicks"
import { STORIES_PANEL_ID, Stories } from "./panels/Stories"
import { TopicMap } from "./panels/TopicMap"
import { WhoWrote } from "./panels/WhoWrote"

export type Side = "left" | "right"

export type RailPanelDef = {
  /** Stable key: persisted in localStorage and sent with analytics. */
  id: string
  title: string
  Component: ComponentType
}

export type RailPanels = Record<Side, RailPanelDef[]>

// Planned: left = "Who wrote this week", "Topic map"; right = "Stories".
// A side with no panels renders nothing at all: no rail, strip or button.
export const LEFT: RailPanelDef[] = [
  {
    id: STORIES_PANEL_ID,
    title: "Stories",
    Component: Stories,
  },
  { id: "who-wrote", title: "Who wrote the wire", Component: WhoWrote },
]
export const RIGHT: RailPanelDef[] = [
  {
    id: "topic-map",
    title: "Topic map",
    Component: TopicMap,
  },
  {
    id: "reader-picks",
    title: "Reader picks",
    Component: ReaderPicks,
  },
]
