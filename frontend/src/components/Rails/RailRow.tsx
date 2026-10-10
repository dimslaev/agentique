import type { AnchorHTMLAttributes, ReactNode } from "react"
import { MiniRail } from "./ScoreMarks"

/** One article in a rail: score rail, "source · date", the title as a link,
 *  and an optional control on the right. Every rail list uses it. */
export function RailRow({
  score,
  source,
  date,
  title,
  href,
  linkProps,
  trailing,
  testId,
}: {
  score: number
  source: string
  date?: string
  title: string
  href: string
  linkProps?: AnchorHTMLAttributes<HTMLAnchorElement>
  trailing?: ReactNode
  testId?: string
}) {
  return (
    <li data-testid={testId} className="flex gap-2.5">
      <MiniRail score={score} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate font-wire text-[10px] uppercase tracking-[0.08em] text-dim">
          {source}
          {date && ` · ${date}`}
        </span>
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          {...linkProps}
          className="text-[13px] leading-snug no-underline [overflow-wrap:anywhere] decoration-muted-foreground underline-offset-[3px] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          {title}
        </a>
      </div>
      {trailing && <div className="shrink-0 self-start pt-0.5">{trailing}</div>}
    </li>
  )
}
