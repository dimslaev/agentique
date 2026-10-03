import { useMutation } from "@tanstack/react-query"
import { CheckCircle2, Loader2 } from "lucide-react"
import { useState } from "react"
import { handleError } from "@/apiError"
import { NewsletterService } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { trackEvent } from "@/lib/analytics"
import { cn } from "@/lib/utils"

// Both states share one bordered box so opening the field shifts nothing.
// 44px tall on phones for touch, 36px from sm up.
const BOX_CLASS = "flex h-11 items-stretch border sm:h-9"

const LABEL_CLASS =
  "flex items-center gap-2 px-4 font-wire text-xs font-bold uppercase tracking-[0.1em] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"

/**
 * An outline "Subscribe" button that opens into an email field on click,
 * so the feed header stays one quiet line until a visitor wants to sign up.
 */
export function InlineSubscribe() {
  const { showErrorToast } = useCustomToast()
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState("")
  const [submitted, setSubmitted] = useState(false)

  const mutation = useMutation({
    mutationFn: () =>
      NewsletterService.subscribe({
        requestBody: { email, categories: ["all"], customCategory: "" },
      }),
    onSuccess: () => setSubmitted(true),
    onError: handleError.bind(showErrorToast),
  })

  if (submitted) {
    return (
      <p className="flex h-11 items-center gap-2 font-wire text-xs uppercase tracking-[0.1em] text-paper sm:h-9">
        <CheckCircle2 className="h-4 w-4 text-signal" />
        Subscribed. Check your inbox.
      </p>
    )
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => {
          trackEvent("newsletter_open_click", { source: "feed" })
          setOpen(true)
        }}
        data-testid="subscribe-open"
        className={cn(
          BOX_CLASS,
          LABEL_CLASS,
          "border-signal text-signal transition-colors hover:bg-signal hover:text-ink",
        )}
      >
        Subscribe
      </button>
    )
  }

  return (
    // Browser validation (type=email, required) catches a bad address on the
    // spot instead of a round trip ending in a toast.
    <form
      onSubmit={(e) => {
        e.preventDefault()
        trackEvent("newsletter_subscribe_click", { source: "feed" })
        mutation.mutate()
      }}
      className={cn(
        BOX_CLASS,
        "w-full border-wire focus-within:border-signal sm:w-80",
      )}
    >
      <input
        type="email"
        required
        // Focus on reveal: the click that opened the field asked for it.
        ref={(el) => el?.focus()}
        placeholder="name@company.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false)
        }}
        onBlur={(e) => {
          // Collapse back if left empty, unless focus moved to the submit.
          if (!email && !e.currentTarget.form?.contains(e.relatedTarget)) {
            setOpen(false)
          }
        }}
        disabled={mutation.isPending}
        autoComplete="email"
        aria-label="Email address"
        // Suppress password-manager icon overlays (1Password, LastPass,
        // Bitwarden, Dashlane) — they clash with the flush field/button seam.
        data-1p-ignore="true"
        data-lpignore="true"
        data-bwignore="true"
        data-form-type="other"
        className="min-w-0 flex-1 bg-transparent px-3 font-wire text-sm text-paper outline-none placeholder:text-dim"
      />
      <button
        type="submit"
        disabled={mutation.isPending}
        className={cn(
          LABEL_CLASS,
          "shrink-0 bg-signal text-ink hover:bg-signal/90 disabled:opacity-70",
        )}
      >
        {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
        Subscribe
      </button>
    </form>
  )
}
