import { Header } from "@/components/Common/Header"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="flex min-h-svh flex-col">
      <Header />
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 md:p-10">
        <div className="w-full max-w-xs">{children}</div>
      </div>
      <Footer />
    </div>
  )
}
