import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { ApiError, LoginService, OpenAPI } from "./client"
import { Toaster } from "./components/ui/sonner"
import "./index.css"
import { trackPageview } from "./lib/analytics"
import { routeTree } from "./routeTree.gen"

OpenAPI.BASE = import.meta.env.VITE_API_URL
OpenAPI.TOKEN = async () => {
  return localStorage.getItem("access_token") || ""
}

const clearSession = () => {
  localStorage.removeItem("access_token")
  window.location.href = "/login"
}

const handleApiError = (error: Error) => {
  if (error instanceof ApiError && [401, 403].includes(error.status)) {
    clearSession()
  }
}

// Renew the session on every visit, so returning readers stay signed in.
if (localStorage.getItem("access_token")) {
  LoginService.refreshToken()
    .then(({ access_token }) =>
      localStorage.setItem("access_token", access_token),
    )
    .catch(handleApiError)
}

const AUTH_FAILURE_STATUSES = [400, 401, 403, 404]

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (
        query.queryKey[0] === "currentUser" &&
        error instanceof ApiError &&
        AUTH_FAILURE_STATUSES.includes(error.status)
      ) {
        clearSession()
        return
      }
      handleApiError(error)
    },
  }),
  mutationCache: new MutationCache({
    onError: handleApiError,
  }),
})

// A deploy deletes the previous build's chunks, so a tab opened before it
// can't load the next route it visits. The router reloads on that itself, but
// only for the error messages it recognises, and Safari words it differently.
// Reload to pick up the new build, at most once every 10s so a chunk that is
// broken for good can't loop.
const RELOAD_KEY = "chunk_reload_at"
window.addEventListener("vite:preloadError", () => {
  const last = Number(sessionStorage.getItem(RELOAD_KEY) ?? 0)
  if (Date.now() - last < 10_000) return
  sessionStorage.setItem(RELOAD_KEY, String(Date.now()))
  window.location.reload()
})

const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

// First-party analytics: log a pageview on every SPA navigation. The path
// only: a sign-in link carries its token in the query string.
router.subscribe("onResolved", ({ toLocation }) => {
  trackPageview(toLocation.pathname)
})

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster richColors closeButton />
    </QueryClientProvider>
  </StrictMode>,
)
