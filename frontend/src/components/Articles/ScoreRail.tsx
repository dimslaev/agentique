import { SCORE_STANDOUT, scoreFraction } from "@/shared/lib/score"
import { cn } from "@/shared/lib/utils"

/**
 * The score rail: a hairline track in the row's left gutter, filled from the
 * bottom in proportion to the article's score. Stacked rows read as a ragged
 * skyline, so a lane's shape tells you how strong its week was before you read
 * a single headline. Standouts (p90+) take the page's only hot colour.
 */
export function ScoreRail({ score }: { score: number }) {
  const standout = score >= SCORE_STANDOUT
  return (
    <div
      aria-hidden
      // The unfilled track has to stay visible: it is the baseline that makes
      // one row's fill comparable to the row above it.
      className="relative w-0.5 shrink-0 self-stretch bg-foreground/12"
    >
      <div
        className={cn(
          "absolute inset-x-0 bottom-0",
          standout ? "bg-primary" : "bg-foreground/40",
        )}
        style={{ height: `${10 + scoreFraction(score) * 90}%` }}
      />
    </div>
  )
}
