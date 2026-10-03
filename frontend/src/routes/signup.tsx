import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"

import { UsersService } from "@/client"
import { EmailLinkForm } from "@/components/Auth/EmailLinkForm"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { isLoggedIn } from "@/hooks/useAuth"
import { trackEvent } from "@/lib/analytics"
import { utmSource } from "@/lib/utm"

export const Route = createFileRoute("/signup")({
  component: SignUp,
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
        title: "Sign Up - agentique",
      },
    ],
  }),
})

function SignUp() {
  return (
    <AuthLayout>
      <EmailLinkForm
        title="Sign up"
        submitLabel="Sign up"
        send={(email) => {
          trackEvent("signup_click", { source: "signup_page" })
          return UsersService.registerUser({
            requestBody: { email, utm_source: utmSource() },
          })
        }}
        footer={
          <>
            Already have an account?{" "}
            <RouterLink to="/login" className="underline underline-offset-4">
              Sign in
            </RouterLink>
          </>
        }
      />
    </AuthLayout>
  )
}
