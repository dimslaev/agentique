import { createFileRoute, Outlet } from "@tanstack/react-router"
import { Footer } from "@/widgets/footer"
import { Header } from "@/widgets/header"

// The sign-in pages: the site header and footer around one narrow column.
export const Route = createFileRoute("/_auth")({
  component: AuthLayout,
})

function AuthLayout() {
  return (
    <div className="flex min-h-svh flex-col">
      <Header />
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 md:p-10">
        <div className="w-full max-w-xs">
          <Outlet />
        </div>
      </div>
      <Footer />
    </div>
  )
}
