import { cn } from "@/lib/utils"

// Scores occupy roughly 20-90 in practice, not the schema's nominal 1-100.
// Normalizing against the real band is what makes the rail readable — against
// 0-100 every bar would cluster mid-track and look identical. These three
// numbers track the live distribution and have to be re-read whenever the
// scoring rubric moves; they were 76/100/92 under the pre-recalibration
// rubric, which put every stored article in the top quarter of the scale.
const SCORE_FLOOR = 20
const SCORE_CEIL = 90
// p90 of the live distribution, and the foot of the rubric's "real technical
// substance, actionable today" band. Above it a row is worth the reader's
// hour, and earns the one hot colour on the page.
export const SCORE_STANDOUT = 80

export function scoreFraction(score: number): number {
  const clamped = Math.min(Math.max(score, SCORE_FLOOR), SCORE_CEIL)
  return (clamped - SCORE_FLOOR) / (SCORE_CEIL - SCORE_FLOOR)
}

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
