// Sponsor slots shown above the feed on the homepage.
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
    slug: "ai-tinkerers-lausanne",
    name: "AI Tinkerers Lausanne",
    blurb: "Meetups for people building with AI — demos, not slides.",
    href: "https://lausanne.aitinkerers.org/",
  },
  {
    slug: "giotto",
    name: "Giotto",
    blurb: "Portable reasoning model — cloud, your GPUs, or on-prem.",
    href: "https://www.giotto.ai/",
  },
]
