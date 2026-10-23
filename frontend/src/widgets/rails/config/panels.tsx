import type { ComponentType } from "react"
import { ReaderPicks } from "../ui/panels/reader-picks"
import { STORIES_PANEL_ID, Stories } from "../ui/panels/stories"
import { Voices } from "../ui/panels/voices"
import { WhoWrote } from "../ui/panels/who-wrote"

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
