// Landing-page sponsor slots. Homepage only — the app shell and /feed stay
// ad-free.
//
// Plain config, edited by hand and deployed with the frontend. There is no
// admin UI and no backend: a sponsor is a name, a line, and a link.

export type SponsorDef = {
  slug: string
  name: string
  blurb: string
  href: string
}

/** Inbox shown in the "Your ad here" dialog. */
export const SPONSOR_EMAIL = "dimitar@agentique.ch"

/**
 * Slots kept in the row. Fewer real sponsors than this and the remainder
 * render as "Your ad here" — an empty row would just be dead space, and the
 * placeholder is the sales pitch.
 */
export const SPONSOR_SLOTS = 3

export const SPONSORS: SponsorDef[] = [
  {
    slug: "swiss-it-forums",
    name: "Swiss IT Forum(s)",
    blurb: "Geneva's IT event — Palexpo, 30 Sep & 1 Oct 2026.",
    href: "https://www.swiss-it-forums.tech/en/",
  },
  {
    slug: "giotto",
    name: "Giotto",
    blurb: "Portable reasoning model — cloud, your GPUs, or on-prem.",
    href: "https://www.giotto.ai/",
  },
]
