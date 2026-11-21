import { createFileRoute, Outlet, useMatches } from "@tanstack/react-router"
import { PageColumn } from "@/shared/ui/page-column"
import { Footer } from "@/widgets/footer"
import { SiteHeader } from "@/widgets/header"

declare module "@tanstack/react-router" {
  interface StaticDataRouteOption {
    /** The page lays out its own width instead of the site's 768px column,
     *  e.g. the feed with its side rails. */
    wide?: boolean
  }
}

// Public shell: every page under it is readable logged out. Pages that need a
// user (profile, admin) guard themselves.
export const Route = createFileRoute("/_layout")({
  component: Layout,
})

function Layout() {
  const wide = useMatches({
    select: (matches) => matches.some((m) => m.staticData?.wide),
  })
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="w-full flex-1 pt-7 pb-12">
        {wide ? (
          <Outlet />
        ) : (
          <PageColumn>
            <Outlet />
          </PageColumn>
        )}
      </main>
      <Footer />
    </div>
  )
}
