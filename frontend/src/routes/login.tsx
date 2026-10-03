import { createFileRoute, redirect } from "@tanstack/react-router"
import { z } from "zod"

import { LoginService } from "@/client"
import { EmailLinkForm } from "@/components/Auth/EmailLinkForm"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { isLoggedIn, rememberRedirect } from "@/hooks/useAuth"

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
          return LoginService.requestSignInLink({ requestBody: { email } })
        }}
      />
    </AuthLayout>
  )
}
