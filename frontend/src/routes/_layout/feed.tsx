import { createFileRoute, redirect } from "@tanstack/react-router"

// The feed moved to "/"; old links and bookmarks still land on it.
export const Route = createFileRoute("/_layout/feed")({
  beforeLoad: () => {
    throw redirect({ to: "/", replace: true })
  },
})
