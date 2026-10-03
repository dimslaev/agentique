import { createFileRoute, Outlet } from "@tanstack/react-router"
import { Footer } from "@/components/Common/Footer"
import { Header } from "@/components/Common/Header"
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
        <Header nav={<UserMenu />} />
        <main className="mx-auto w-full max-w-3xl flex-1 px-4 pt-7 pb-12">
          <Outlet />
        </main>
        <Footer />
      </div>
    </FiltersProvider>
  )
}
