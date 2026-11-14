import { createFileRoute, redirect } from "@tanstack/react-router"

// The page moved to /connect. Old links still land.
export const Route = createFileRoute("/_layout/developers")({
  beforeLoad: () => {
    throw redirect({ to: "/connect", replace: true })
  },
})
