import type { ComponentType } from "react"
import { ReaderPicks } from "./panels/ReaderPicks"
import { STORIES_PANEL_ID, Stories } from "./panels/Stories"
import { Voices } from "./panels/Voices"
import { WhoWrote } from "./panels/WhoWrote"

export type Side = "left" | "right"

export type RailPanelDef = {
  /** Stable key: persisted in localStorage and sent with analytics. */
  id: string
  title: string
  Component: ComponentType
}

export type RailPanels = Record<Side, RailPanelDef[]>

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
  { id: "voices", title: "Voices", Component: Voices },
  {
    id: "reader-picks",
    title: "Reader picks",
    Component: ReaderPicks,
  },
]
