import { createFileRoute, redirect } from "@tanstack/react-router"

import { AnalyticsDashboard } from "@/components/Admin/AnalyticsDashboard"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/admin")({
  component: AnalyticsDashboard,
  beforeLoad: async ({ location }) => {
    if (!isLoggedIn()) {
      throw redirect({ to: "/login", search: { redirect: location.href } })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Analytics - agentique",
      },
    ],
  }),
})
