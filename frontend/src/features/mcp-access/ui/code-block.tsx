import { useState } from "react"
import { cn } from "@/shared/lib/utils"

/** Text to copy, with a label saying what it is or where it goes. Prose wraps;
 *  code keeps its lines and scrolls sideways. */
export function CodeBlock({
  code,
  label,
  prose = false,
}: {
  code: string
  label: string
  prose?: boolean
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="flex items-center justify-between gap-4 border-b pl-4">
        <span className="truncate font-wire text-xs text-muted-foreground">
          {label}
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label={`Copy ${label}`}
          className="h-9 shrink-0 px-4 font-wire text-xs uppercase tracking-[0.08em] text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        className={cn(
          "px-4 py-3 text-foreground",
          prose
            ? "whitespace-pre-wrap font-sans text-sm leading-relaxed"
            : "overflow-x-auto font-wire text-xs leading-relaxed",
        )}
      >
        {code}
      </pre>
    </div>
  )
}
