import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { NewsletterService } from "@/client"
import { Footer } from "@/components/Common/Footer"
import { Logo } from "@/components/Common/Logo"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/")({
  component: Landing,
  head: () => ({
    meta: [{ title: "Agentique - AI news for developers" }],
  }),
})

const formSchema = z.object({
  email: z.string().email({ message: "Valid email is required" }),
})
type FormData = z.infer<typeof formSchema>

function NewsletterField() {
  const { showErrorToast } = useCustomToast()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: { email: "" },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) => {
      const utm_source =
        new URLSearchParams(window.location.search).get("utm_source") ??
        undefined
      return NewsletterService.subscribe({
        requestBody: {
          email: data.email,
          categories: ["all"],
          customCategory: "",
          ...(utm_source && { utm_source }),
        },
      })
    },
    onError: handleError.bind(showErrorToast),
  })

  if (mutation.isSuccess) {
    return (
      <p className="text-sm font-medium" data-testid="newsletter-success">
        You&apos;re subscribed. Check your inbox.
      </p>
    )
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
        noValidate
        className="flex flex-col gap-2 sm:flex-row sm:items-start"
      >
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem className="flex-1">
              <FormControl>
                <Input
                  type="email"
                  placeholder="your@email.com"
                  disabled={mutation.isPending}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <LoadingButton type="submit" loading={mutation.isPending}>
          Subscribe
        </LoadingButton>
      </form>
    </Form>
  )
}

function Landing() {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Logo />
          <nav className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link to="/login">Log in</Link>
            </Button>
            <Button asChild size="sm">
              <Link to="/signup">Sign up</Link>
            </Button>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-3xl px-4 py-16 md:py-24">
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Every AI story that matters. For devs.
          </h1>
          <p className="text-muted-foreground mt-4 max-w-xl text-base">
            Agentique curates the AI news developers can act on. Subscribe to
            the newsletter, or sign up for the full feed.
          </p>

          <div className="mt-8 max-w-md">
            <NewsletterField />
          </div>

          <p className="text-muted-foreground mt-6 text-sm">
            Want the full feed?{" "}
            <Link
              to="/signup"
              className="text-foreground underline underline-offset-4"
            >
              Sign up
            </Link>
          </p>
        </div>
      </main>

      <Footer />
    </div>
  )
}
