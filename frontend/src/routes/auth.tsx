import { useMutation } from "@tanstack/react-query"
import {
  createFileRoute,
  Link as RouterLink,
  useNavigate,
} from "@tanstack/react-router"
import { useEffect } from "react"
import { z } from "zod"

import { AuthLayout } from "@/components/Common/AuthLayout"
import { signInWithLink, takeRedirect } from "@/hooks/useAuth"

const searchSchema = z.object({
  token: z.string().catch(""),
})

export const Route = createFileRoute("/auth")({
  component: Auth,
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      {
        title: "Signing in - agentique",
      },
    ],
  }),
})

// Where the sign-in link in every email lands: swap its token for an access
// token, then go where the reader was headed.
function Auth() {
  const { token } = Route.useSearch()
  const navigate = useNavigate()
  const mutation = useMutation({
    mutationFn: signInWithLink,
    onSuccess: () => navigate({ href: takeRedirect() ?? "/", replace: true }),
  })
  const { mutate } = mutation

  useEffect(() => {
    if (token) mutate(token)
  }, [token, mutate])

  if (token && !mutation.isError) {
    return (
      <AuthLayout>
        <p className="text-center text-sm text-muted-foreground">
          Signing you in…
        </p>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <div className="flex flex-col gap-2 text-center">
        <h1 className="font-display text-2xl font-bold tracking-tight">
          This link doesn't work
        </h1>
        <p className="text-sm text-muted-foreground">
          It's invalid or has expired.{" "}
          <RouterLink to="/login" className="underline underline-offset-4">
            Get a new link
          </RouterLink>
        </p>
      </div>
    </AuthLayout>
  )
}
