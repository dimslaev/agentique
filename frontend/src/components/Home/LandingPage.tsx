import { useMutation } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ArrowUp, CheckCircle2, Moon, Sun } from "lucide-react"
import { useState } from "react"

import { NewsletterService } from "@/client"
import { useTheme } from "@/components/theme-provider"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { trackEvent } from "@/lib/analytics"
import { handleError } from "@/utils"
import { SponsorRow } from "./SponsorRow"
import { TopicLanes } from "./TopicLanes"

export function LandingPage() {
  return (
    <div className="landing flex min-h-screen flex-col">
      <LandingHeader />
      <main className="flex-1">
        <div className="mx-auto w-full max-w-5xl px-6 sm:px-8">
          <Hero />
          <SponsorRow />
          <TopicLanes />
        </div>
      </main>
      <footer className="mt-16 border-t border-wire">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6 sm:px-8">
          <span className="font-wire text-[10px] uppercase tracking-[0.12em] text-dim">
            agentique
          </span>
          <button
            type="button"
            aria-label="Scroll back to top"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="flex h-8 w-8 items-center justify-center border border-wire text-dim transition-colors hover:border-signal hover:text-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
      </footer>
    </div>
  )
}

function LandingHeader() {
  const { resolvedTheme, setTheme } = useTheme()

  return (
    <header className="border-b border-wire">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-3 sm:px-8">
        <Link
          to="/"
          className="font-display text-base font-extrabold lowercase tracking-[-0.01em] text-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
        >
          agentique
        </Link>
        <nav className="flex items-center gap-5">
          <Link
            to="/feed"
            className="font-wire text-[11px] uppercase tracking-[0.12em] text-dim transition-colors hover:text-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
          >
            Feed
          </Link>
          <button
            type="button"
            data-testid="theme-button"
            aria-label="Toggle theme"
            onClick={() =>
              setTheme(resolvedTheme === "dark" ? "light" : "dark")
            }
            className="flex h-7 w-7 items-center justify-center text-dim transition-colors hover:text-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
          >
            {resolvedTheme === "dark" ? (
              <Moon className="h-4 w-4" />
            ) : (
              <Sun className="h-4 w-4" />
            )}
          </button>
        </nav>
      </div>
    </header>
  )
}

function Hero() {
  return (
    <div className="flex flex-col gap-8 pb-14 pt-16 sm:pb-16 sm:pt-24">
      <div className="flex flex-col gap-5">
        <h1 className="font-display text-[2rem] font-extrabold leading-[1.05] tracking-[-0.02em] text-paper sm:text-[3.5rem]">
          <span className="text-signal">&gt;</span> Every AI story that matters.
          <br />
          For devs.
          <span className="caret ml-1 text-signal">_</span>
        </h1>
        <p className="max-w-xl text-[15px] leading-relaxed text-dim">
          Agentique reads 1,000+ articles, repos, and papers a day and scores
          every one against a single question: can a developer act on this
          today? The bar on each headline is that score.
        </p>
      </div>
      <NewsletterSignup />
    </div>
  )
}

function NewsletterSignup() {
  const { showErrorToast } = useCustomToast()
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
      <p className="flex items-center gap-2 font-wire text-xs uppercase tracking-[0.1em] text-paper">
        <CheckCircle2 className="h-4 w-4 text-signal" />
        Subscribed. Check your inbox.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (email) {
            trackEvent("newsletter_subscribe_click", { source: "landing" })
            mutation.mutate()
          }
        }}
        className="flex w-full max-w-md items-stretch border border-wire focus-within:border-signal"
        noValidate
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
          className="h-11 min-w-0 flex-1 bg-transparent px-4 font-wire text-sm text-paper outline-none placeholder:text-dim"
        />
        <LoadingButton
          type="submit"
          loading={mutation.isPending}
          // text-ink, not a fixed hex: it flips with the theme so the label
          // stays legible on both the bright and the dark orange.
          className="h-11 shrink-0 rounded-none bg-signal px-5 font-wire text-xs font-bold uppercase tracking-[0.1em] text-ink hover:bg-signal/90"
        >
          Subscribe
        </LoadingButton>
      </form>
      <p className="font-wire text-[11px] text-dim">
        Or{" "}
        <Link
          to="/feed"
          className="text-paper no-underline transition-colors hover:text-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
        >
          browse the full feed
        </Link>{" "}
        — filter by tag, kind, and score.
      </p>
    </div>
  )
}
