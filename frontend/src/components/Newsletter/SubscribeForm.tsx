import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { NewsletterService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const CATEGORIES = ["all", "models", "dev", "research"] as const

const formSchema = z.object({
  email: z.string().email({ message: "Valid email is required" }),
  customCategory: z.string().optional(),
})
type FormData = z.infer<typeof formSchema>

export function SubscribeForm() {
  const { showErrorToast } = useCustomToast()
  const [categories, setCategories] = useState<string[]>(["all"])
  const [submitted, setSubmitted] = useState(false)

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: { email: "", customCategory: "" },
  })

  function toggleCategory(cat: string) {
    if (cat === "all") {
      setCategories(["all"])
      return
    }
    setCategories((prev) => {
      const without = prev.filter((c) => c !== "all" && c !== cat)
      if (prev.includes(cat)) {
        return without.length === 0 ? ["all"] : without
      }
      return [...without, cat]
    })
  }

  const mutation = useMutation({
    mutationFn: (data: FormData) => {
      const utm_source =
        new URLSearchParams(window.location.search).get("utm_source") ??
        undefined
      return NewsletterService.subscribe({
        requestBody: {
          email: data.email,
          categories,
          customCategory: data.customCategory ?? "",
          ...(utm_source && { utm_source }),
        },
      })
    },
    onSuccess: () => setSubmitted(true),
    onError: handleError.bind(showErrorToast),
  })

  if (submitted) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <p className="text-sm font-medium">You&apos;re subscribed.</p>
          <p className="text-muted-foreground mt-1 text-xs">
            You can update your preferences any time by submitting this form
            again.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
            noValidate
            className="flex flex-col gap-5"
          >
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email *</FormLabel>
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

            <div>
              <Label className="mb-2">Interested in</Label>
              <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((cat) => (
                  <Button
                    key={cat}
                    type="button"
                    variant={categories.includes(cat) ? "default" : "outline"}
                    size="sm"
                    className="capitalize"
                    onClick={() => toggleCategory(cat)}
                  >
                    {cat}
                  </Button>
                ))}
              </div>
            </div>

            <FormField
              control={form.control}
              name="customCategory"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Custom interest</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="e.g. Swiss AI, open source, privacy"
                      rows={2}
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
      </CardContent>
    </Card>
  )
}
