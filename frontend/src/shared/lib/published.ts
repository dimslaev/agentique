/** The Published filter's windows, in days. The left rail's panels follow it. */
export const PUBLISHED_DAYS: Record<string, number> = {
  "3d": 3,
  "1w": 7,
  "1m": 30,
}

export function cutoffIso(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString()
}
