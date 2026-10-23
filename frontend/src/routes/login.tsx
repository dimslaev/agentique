import { createFileRoute, redirect } from "@tanstack/react-router"
import { z } from "zod"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { EmailLinkForm } from "@/features/sign-in"
import { LoginService } from "@/shared/api"
import { isLoggedIn, rememberRedirect } from "@/shared/auth"
import { utmSource } from "@/shared/lib/utm"

const searchSchema = z.object({
  redirect: z.string().optional(),
})

export const Route = createFileRoute("/login")({
  component: Login,
  validateSearch: searchSchema,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Sign In - agentique",
      },
    ],
  }),
})

function Login() {
  const { redirect: redirectTo } = Route.useSearch()

  return (
    <AuthLayout>
      <EmailLinkForm
        title="Sign in"
        submitLabel="Email me a sign-in link"
        send={(email) => {
          rememberRedirect(redirectTo)
          return LoginService.requestSignInLink({
            requestBody: { email, utm_source: utmSource() },
          })
        }}
      />
    </AuthLayout>
  )
}
