import { createFileRoute } from "@tanstack/react-router"

import { LandingPage } from "@/components/Home/LandingPage"

export const Route = createFileRoute("/home")({
  component: LandingPage,
  head: () => ({
    meta: [{ title: "Agentique - AI news for developers" }],
  }),
})
