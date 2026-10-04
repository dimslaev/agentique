import { formatCount } from "./format"

export type RankedRow = {
  key: string
  label: string
  count: number
  visitors: number
}

/** A top-N list: label, count and distinct visitors, each row underlined by a
 *  bar in proportion to the busiest row. */
export function RankedTable({
  title,
  labelHeading,
  countHeading,
  rows,
}: {
  title: string
  labelHeading: string
  countHeading: string
  rows: RankedRow[]
}) {
  const max = Math.max(1, ...rows.map((r) => r.count))
  return (
    <section className="flex min-w-0 flex-col gap-2">
      <h2 className="font-wire text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
        {title}
      </h2>
      {rows.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">Nothing yet.</p>
      ) : (
        <table className="w-full table-fixed text-sm">
          <thead className="font-wire text-[10px] text-muted-foreground">
            <tr className="border-b border-border">
              <th className="py-1 text-left font-normal">{labelHeading}</th>
              <th className="w-16 py-1 text-right font-normal">
                {countHeading}
              </th>
              <th className="w-16 py-1 text-right font-normal">Visitors</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-b border-border/60">
                <td className="py-1.5 pr-3">
                  <div className="truncate" title={r.label}>
                    {r.label}
                  </div>
                  <div
                    aria-hidden
                    className="mt-1 h-0.5 bg-foreground/30"
                    style={{ width: `${(r.count / max) * 100}%` }}
                  />
                </td>
                <td className="py-1.5 text-right align-top font-wire text-xs tabular-nums">
                  {formatCount(r.count)}
                </td>
                <td className="py-1.5 text-right align-top font-wire text-xs tabular-nums text-muted-foreground">
                  {formatCount(r.visitors)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
