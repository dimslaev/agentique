import { createFileRoute, Outlet, useMatches } from "@tanstack/react-router"
import { Footer } from "@/components/Common/Footer"
import { Header } from "@/components/Common/Header"
import { PageColumn } from "@/components/Common/PageColumn"
import { UserMenu } from "@/components/Common/UserMenu"
import { RailsProvider } from "@/components/Rails/RailsProvider"
import { RailToggles } from "@/components/Rails/RailToggles"
import { FiltersProvider } from "@/context/filters"

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
    <FiltersProvider>
      <RailsProvider>
        <div className="flex min-h-screen flex-col">
          <Header
            nav={
              <>
                <RailToggles />
                <UserMenu />
              </>
            }
          />
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
      </RailsProvider>
    </FiltersProvider>
  )
}
