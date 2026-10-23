import { useState } from "react"

export function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // noop
    }
  }

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      <div className="flex justify-end border-b px-4 py-2">
        <button
          type="button"
          onClick={copy}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3 font-wire text-xs leading-relaxed text-foreground">
        {code}
      </pre>
    </div>
  )
}
