import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { handleError } from "@/apiError"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"

const formSchema = z.object({
  email: z.email({ message: "Invalid email address" }),
})

type FormData = z.infer<typeof formSchema>

interface EmailLinkFormProps {
  title: string
  submitLabel: string
  send: (email: string) => Promise<unknown>
}

/**
 * One email field that asks the backend to email a sign-in link, then
 * swaps itself for a "check your inbox" note. `send` picks the endpoint.
 */
export function EmailLinkForm({
  title,
  submitLabel,
  send,
}: EmailLinkFormProps) {
  const { showErrorToast } = useCustomToast()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: { email: "" },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) => send(data.email),
    onError: handleError.bind(showErrorToast),
  })

  if (mutation.isSuccess) {
    return (
      <div className="flex flex-col gap-2 text-center">
        <h1 className="font-display text-2xl font-bold tracking-tight">
          Check your inbox
        </h1>
        <p className="text-sm text-muted-foreground" data-testid="link-sent">
          We sent a sign-in link to {mutation.variables?.email}.
        </p>
      </div>
    )
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit((data) => {
          if (!mutation.isPending) mutation.mutate(data)
        })}
        className="flex flex-col gap-6"
      >
        <h1 className="text-center font-display text-2xl font-bold tracking-tight">
          {title}
        </h1>

        <div className="grid gap-4">
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    data-testid="email-input"
                    placeholder="user@example.com"
                    type="email"
                    autoComplete="email"
                    {...field}
                  />
                </FormControl>
                <FormMessage className="text-xs" />
              </FormItem>
            )}
          />

          <LoadingButton type="submit" loading={mutation.isPending}>
            {submitLabel}
          </LoadingButton>
        </div>
      </form>
    </Form>
  )
}
