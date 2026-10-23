export function formatCount(n: number): string {
  return n.toLocaleString("en-US")
}

/** A report day is a UTC calendar date, so it is formatted in UTC too: in the
 *  reader's own zone "2026-10-04" can render as Oct 3. */
export function formatDay(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  })
}
