import { useMutation } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ArrowUp } from "lucide-react"
import { useState } from "react"

import { NewsletterService } from "@/client"
import { Header } from "@/components/Common/Header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { trackEvent } from "@/lib/analytics"
import { handleError } from "@/utils"
import { SourceBoxes } from "./SourceBoxes"

export function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header nav={<LandingNav />} />
      <main className="flex-1 px-6 py-16">
        <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-16">
          <div className="flex w-full max-w-xl flex-col items-center gap-6 text-center">
            <Hero />
            {/* --- BUTTON 1: newsletter signup (logic owned by routing agent) --- */}
            <NewsletterSignup />
            {/* --- BUTTON 2: into the app (logic owned by routing agent) --- */}
            <FeedCta />
          </div>
          <SourceBoxes />
        </div>
      </main>
      <footer className="border-t">
        <div className="mx-auto flex w-full max-w-5xl justify-center px-6 py-6">
          <button
            type="button"
            aria-label="Scroll back to top"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="flex h-9 w-9 items-center justify-center rounded-full border text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
      </footer>
    </div>
  )
}

function LandingNav() {
  return (
    <Button size="sm" asChild>
      <Link to="/feed">Feed</Link>
    </Button>
  )
}

function Hero() {
  return (
    <div className="flex flex-col gap-4">
      <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
        AI news for developers
      </p>
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
        Every AI story that matters. For devs.
      </h1>
      <p className="text-muted-foreground">
        Agentique ingests 1,000+ articles, tweets, and discussions every day and
        runs them through an AI pipeline built to answer one question: can a
        developer act on this today?
      </p>
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
      <p className="text-sm font-medium">
        You&apos;re subscribed. Check your inbox.
      </p>
    )
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (email) {
          trackEvent("newsletter_subscribe_click", { source: "landing" })
          mutation.mutate()
        }
      }}
      className="flex w-full max-w-md items-center rounded-full border border-input bg-transparent shadow-xs transition-[color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50"
      noValidate
    >
      <Input
        type="email"
        required
        placeholder="your@email.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        disabled={mutation.isPending}
        autoComplete="email"
        // Suppress password-manager icon overlays (1Password, LastPass,
        // Bitwarden, Dashlane) — they clash with the merged pill shape.
        data-1p-ignore="true"
        data-lpignore="true"
        data-bwignore="true"
        data-form-type="other"
        className="h-11 flex-1 rounded-full border-0 bg-transparent pl-5 pr-3 text-base shadow-none dark:bg-transparent focus-visible:ring-0"
      />
      <LoadingButton
        type="submit"
        loading={mutation.isPending}
        className="my-1 mr-1 h-9 shrink-0 rounded-full px-6"
      >
        Subscribe
      </LoadingButton>
    </form>
  )
}

function FeedCta() {
  return (
    <p className="text-sm text-muted-foreground">
      Want the full feed?{" "}
      <Link to="/feed" className="text-foreground underline underline-offset-4">
        Browse it now
      </Link>
    </p>
  )
}
