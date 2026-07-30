import { cn } from "@/lib/utils"

// The pipeline's scores occupy 76-100 in practice, not the schema's nominal
// 1-100. Normalizing against the real band is what makes the rail readable —
// against 0-100 every bar would sit in the top quarter and look identical.
const SCORE_FLOOR = 76
const SCORE_CEIL = 100
// p75 of the live distribution. Above it a row is worth the reader's hour, and
// earns the one hot colour on the page.
const SCORE_STANDOUT = 92

export function scoreFraction(score: number): number {
  const clamped = Math.min(Math.max(score, SCORE_FLOOR), SCORE_CEIL)
  return (clamped - SCORE_FLOOR) / (SCORE_CEIL - SCORE_FLOOR)
}

/**
 * The score rail: a hairline track in the row's left gutter, filled from the
 * bottom in proportion to the article's score. Stacked rows read as a ragged
 * skyline, so a lane's shape tells you how strong its week was before you read
 * a single headline. Standouts (p75+) take the page's only hot colour.
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
