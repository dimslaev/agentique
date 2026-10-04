import { useMutation } from "@tanstack/react-query"
import { CheckCircle2, Loader2 } from "lucide-react"
import { useState } from "react"
import { handleError } from "@/apiError"
import { UsersService } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { trackEvent } from "@/lib/analytics"
import { utmSource } from "@/lib/utm"

/**
 * A bordered bar at the top of the feed: a short pitch and an email field, on
 * one line from md up and stacked on phones.
 * Signing up creates the account, subscribes to the newsletter, and emails the
 * sign-in link. The field is 44px tall on phones for touch, 40px from md up.
 */
export function SignupPanel() {
  const { showErrorToast } = useCustomToast()
  const [email, setEmail] = useState("")

  const mutation = useMutation({
    mutationFn: () =>
      UsersService.registerUser({
        requestBody: { email, utm_source: utmSource() },
      }),
    onError: handleError.bind(showErrorToast),
  })

  return (
    <section
      aria-label="Sign up"
      data-testid="signup-panel"
      className="mb-5 flex flex-col border border-wire md:h-10 md:flex-row md:items-center md:gap-4 md:pl-3"
    >
      {/* One line from md up; on phones the pitch sits above the field. */}
      <p className="flex min-w-0 flex-1 items-center gap-2 truncate px-3 py-2.5 font-wire text-[10px] uppercase tracking-[0.04em] text-dim md:p-0 md:text-[11px] md:tracking-[0.1em]">
        <span className="inline-block h-1.5 w-1.5 shrink-0 bg-signal" />
        <span className="truncate">
          <span className="text-paper">AI news for builders</span> · Sign up for
          full access
        </span>
      </p>

      {mutation.isSuccess ? (
        <p className="flex h-11 flex-1 items-center gap-2 border-t border-wire px-3 font-wire md:h-full md:justify-end md:border-t-0 md:pl-0 text-[11px] uppercase tracking-[0.1em] text-paper">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-signal" />
          Check your inbox
        </p>
      ) : (
        // Browser validation (type=email, required) catches a bad address on
        // the spot instead of a round trip ending in a toast.
        <form
          onSubmit={(e) => {
            e.preventDefault()
            trackEvent("signup_click", { source: "feed" })
            mutation.mutate()
          }}
          className="flex h-11 items-stretch border-t border-wire md:h-full md:w-72 md:flex-none md:border-t-0"
        >
          <input
            type="email"
            required
            placeholder="name@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={mutation.isPending}
            autoComplete="email"
            aria-label="Email address"
            // Suppress password-manager icon overlays (1Password, LastPass,
            // Bitwarden, Dashlane) — they clash with the flush field/button seam.
            data-1p-ignore="true"
            data-lpignore="true"
            data-bwignore="true"
            data-form-type="other"
            className="min-w-0 flex-1 bg-transparent px-3 font-wire text-base text-paper outline-none placeholder:text-dim md:border-l md:border-wire md:text-sm"
          />
          <button
            type="submit"
            disabled={mutation.isPending}
            className="flex shrink-0 items-center gap-2 bg-signal px-4 font-wire text-[11px] font-bold uppercase tracking-[0.1em] text-ink transition-colors hover:bg-signal/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal disabled:opacity-70"
          >
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Sign up
          </button>
        </form>
      )}
    </section>
  )
}
