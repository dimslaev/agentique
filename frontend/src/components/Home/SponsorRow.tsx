import { Check, Copy } from "lucide-react"
import { useState } from "react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import { trackEvent } from "@/lib/analytics"
import { cn } from "@/lib/utils"
import { SPONSOR_EMAIL, SPONSOR_SLOTS, SPONSORS } from "./sponsors"

/**
 * Sponsor row. Horizontal on every width — on narrow screens it stays a row
 * and scrolls sideways rather than stacking, so it never grows into a wall of
 * ads above the wire.
 */
export function SponsorRow() {
  const [contactOpen, setContactOpen] = useState(false)
  const placeholders = Math.max(0, SPONSOR_SLOTS - SPONSORS.length)

  return (
    <section aria-label="Sponsors" className="w-full pb-12">
      {/* Bleeds to the viewport edge on mobile (the page gutter is px-6) so a
          half-visible card signals "scrollable" instead of looking clipped. */}
      <ul className="-mx-6 flex snap-x snap-mandatory gap-3 overflow-x-auto px-6 pb-1 [scrollbar-width:none] sm:mx-0 sm:px-0 [&::-webkit-scrollbar]:hidden">
        {SPONSORS.map((sponsor) => (
          <li key={sponsor.slug} className={SLOT_CLASS}>
            <a
              href={sponsor.href}
              target="_blank"
              rel="noreferrer sponsored"
              onClick={() =>
                trackEvent("sponsor_click", { slug: sponsor.slug })
              }
              data-testid="sponsor-slot"
              className={cn(BOX_CLASS, "border-wire")}
            >
              <SlotBody name={sponsor.name} blurb={sponsor.blurb} />
            </a>
          </li>
        ))}
        {Array.from({ length: placeholders }, (_, i) => (
          <li key={`open-${i}`} className={SLOT_CLASS}>
            {/* Button, not a mailto: a dialog beats firing an empty mail client
                for a visitor who is only curious what a slot costs. */}
            <button
              type="button"
              onClick={() => {
                trackEvent("sponsor_slot_click")
                setContactOpen(true)
              }}
              data-testid="sponsor-slot-open"
              className={cn(BOX_CLASS, "border-dashed border-wire text-left")}
            >
              <SlotBody
                name="Your ad here"
                blurb="Reach developers who ship with AI every day."
                placeholder
              />
            </button>
          </li>
        ))}
      </ul>

      <ContactDialog open={contactOpen} onOpenChange={setContactOpen} />
    </section>
  )
}

const SLOT_CLASS = "w-[15rem] shrink-0 snap-start sm:w-auto sm:flex-1"

const BOX_CLASS =
  "flex h-full w-full min-h-[5.5rem] flex-col gap-1.5 border p-4 transition-colors hover:border-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"

function SlotBody({
  name,
  blurb,
  placeholder,
}: {
  name: string
  blurb: string
  placeholder?: boolean
}) {
  return (
    <>
      <span className="flex items-center gap-1.5 font-wire text-[10px] uppercase tracking-[0.12em] text-dim">
        <span
          className={cn(
            "inline-block h-1.5 w-1.5 shrink-0",
            placeholder ? "bg-wire" : "bg-signal",
          )}
        />
        Sponsor
      </span>
      <span
        className={cn(
          "line-clamp-1 font-display text-[13px] font-bold uppercase tracking-[0.08em]",
          placeholder ? "text-dim" : "text-paper",
        )}
      >
        {name}
      </span>
      <span className="line-clamp-2 text-xs leading-snug text-dim">
        {blurb}
      </span>
    </>
  )
}

function ContactDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [copied, copy] = useCopyToClipboard()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="sponsor-contact-dialog"
        className="border-wire bg-ink sm:max-w-md"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-base font-extrabold uppercase tracking-[0.08em] text-paper">
            Sponsor agentique
          </DialogTitle>
          <DialogDescription className="text-sm leading-relaxed text-dim">
            Write to the address below with what you want to promote and which
            weeks you have in mind. You get a reply with slots and pricing.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-stretch border border-wire">
          <a
            href={`mailto:${SPONSOR_EMAIL}?subject=Sponsoring%20agentique`}
            onClick={() => trackEvent("sponsor_contact_mail")}
            className="flex min-w-0 flex-1 items-center px-4 font-wire text-sm text-paper no-underline transition-colors hover:text-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
          >
            <span className="truncate">{SPONSOR_EMAIL}</span>
          </a>
          <button
            type="button"
            aria-label="Copy email address"
            onClick={() => void copy(SPONSOR_EMAIL)}
            className="flex h-11 w-11 shrink-0 items-center justify-center border-l border-wire text-dim transition-colors hover:text-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
          >
            {copied ? (
              <Check className="h-4 w-4 text-signal" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
