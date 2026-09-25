import { createFileRoute, Outlet } from "@tanstack/react-router"
import { Appearance } from "@/components/Common/Appearance"
import { Footer } from "@/components/Common/Footer"
import { Logo } from "@/components/Common/Logo"
import { UserMenu } from "@/components/Common/UserMenu"
import { FiltersProvider } from "@/context/filters"

// Public shell: every page under it is readable logged out. Pages that need a
// user (profile, admin) guard themselves.
export const Route = createFileRoute("/_layout")({
  component: Layout,
})

function Layout() {
  return (
    <FiltersProvider>
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-10 shrink-0 border-b bg-background">
          <div className="mx-auto flex h-12 max-w-3xl items-center gap-4 px-4">
            <Logo full className="-ml-2" />
            <div className="ml-auto flex items-center gap-3">
              <Appearance />
              <UserMenu />
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-3xl flex-1 px-4 pt-7 pb-12">
          <Outlet />
        </main>
        <Footer />
      </div>
    </FiltersProvider>
  )
}
