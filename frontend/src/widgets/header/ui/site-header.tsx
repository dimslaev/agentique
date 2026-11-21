import { Link, useRouterState } from "@tanstack/react-router"
import { cn } from "@/shared/lib/utils"
import { RailToggles } from "@/widgets/rails"
import { Header } from "./header"
import { UserMenu } from "./user-menu"

// The site nav, the same links the blog's static header shows (see
// frontend/scripts/prerender-blog.ts), so moving between the two feels like
// one site.
const NAV_LINK =
  "inline-flex h-12 items-center font-wire text-[11px] uppercase tracking-[0.08em] transition-colors hover:text-foreground"
const NAV_CURRENT = "text-paper shadow-[inset_0_-2px_0_var(--signal)]"

/** The site header with nav, rail toggles and the user menu — shared by the
 *  main shell and the sign-in pages. */
export function SiteHeader() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const onFeed = pathname === "/"
  const onMcp = pathname === "/connect-mcp"
  return (
    <Header
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
            {/* /connect-mcp is readable logged out — it explains MCP and has
             *  its own sign-up CTA, so no login detour. */}
            <Link
              to="/connect-mcp"
              className={cn(NAV_LINK, onMcp ? NAV_CURRENT : "text-dim")}
              aria-current={onMcp ? "page" : undefined}
            >
              MCP
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
