import {
  createFileRoute,
  Link,
  Outlet,
  useMatches,
  useRouterState,
} from "@tanstack/react-router"
import { Footer } from "@/components/Common/Footer"
import { Header } from "@/components/Common/Header"
import { PageColumn } from "@/components/Common/PageColumn"
import { UserMenu } from "@/components/Common/UserMenu"
import { RailsProvider, useRails } from "@/components/Rails/RailsProvider"
import { RailToggles } from "@/components/Rails/RailToggles"
import { FiltersProvider } from "@/context/filters"
import { cn } from "@/lib/utils"

declare module "@tanstack/react-router" {
  interface StaticDataRouteOption {
    /** The page lays out its own width instead of the site's 768px column,
     *  e.g. the feed with its side rails. */
    wide?: boolean
  }
}

// The site nav, the same pair the blog's static header shows (see
// frontend/scripts/prerender-blog.ts), so moving between the two feels like
// one site.
const NAV_LINK =
  "inline-flex h-11 items-center font-wire text-[11px] uppercase tracking-[0.08em] transition-colors hover:text-foreground"
const NAV_CURRENT = "text-paper shadow-[inset_0_-2px_0_var(--signal)]"

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
      </RailsProvider>
    </FiltersProvider>
  )
}

/** On wide screens with inline rails, the header spans them too. */
function SiteHeader() {
  const { mode, present, hasPanels } = useRails()
  const onFeed = useRouterState({
    select: (s) => s.location.pathname === "/",
  })
  const wide =
    present && mode === "wide" && (hasPanels("left") || hasPanels("right"))
  return (
    <Header
      wide={wide}
      nav={
        <>
          <nav aria-label="Site" className="flex items-center gap-5">
            <Link
              to="/"
              className={cn(NAV_LINK, onFeed ? NAV_CURRENT : "text-dim")}
              aria-current={onFeed ? "page" : undefined}
            >
              Feed
            </Link>
            {/* /blog/ is prerendered outside the router: a plain anchor, and
             *  never the current page while the router is mounted. */}
            <a href="/blog/" className={cn(NAV_LINK, "text-dim")}>
              Blog
            </a>
          </nav>
          <RailToggles />
          <UserMenu />
        </>
      }
    />
  )
}
