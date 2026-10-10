import { SCORE_STANDOUT, scoreFraction } from "@/components/Articles/ScoreRail"
import { cn } from "@/lib/utils"

// Marks every rail panel draws scores with. Both read the feed's own rule
// (scoreFraction, SCORE_STANDOUT) so a score looks the same beside the wire
// as it does on it.

/** One score as a vertical 2px bar, stretched to its row's height. */
export function MiniRail({
  score,
  className,
}: {
  score: number
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "relative block w-0.5 shrink-0 self-stretch bg-foreground/12",
        className,
      )}
    >
      <span
        className={cn(
          "absolute inset-x-0 bottom-0",
          score >= SCORE_STANDOUT ? "bg-primary" : "bg-foreground/40",
        )}
        style={{ height: `${10 + scoreFraction(score) * 90}%` }}
      />
    </span>
  )
}

/** A row of tiny bars, one per score, in the order given: a skyline. */
export function ScoreBars({
  scores,
  className,
}: {
  scores: number[]
  className?: string
}) {
  return (
    <span
      aria-hidden
      className={cn("flex h-[18px] shrink-0 items-end gap-0.5", className)}
    >
      {scores.map((score, i) => (
        <span
          key={i}
          className={cn(
            "block w-0.5",
            score >= SCORE_STANDOUT ? "bg-primary" : "bg-foreground/40",
          )}
          style={{ height: `${2 + scoreFraction(score) * 16}px` }}
        />
      ))}
    </span>
  )
}
