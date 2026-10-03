import { Logo } from "@/components/Common/Logo"

interface HeaderProps {
  nav?: React.ReactNode
}

// Site header shared by the feed shell and the auth pages.
export function Header({ nav }: HeaderProps) {
  return (
    <header className="sticky top-0 z-10 shrink-0 border-b bg-background">
      <div className="mx-auto flex h-12 max-w-3xl items-center gap-4 px-4">
        <Logo full className="-ml-2" />
        <div className="ml-auto flex items-center gap-3">{nav}</div>
      </div>
    </header>
  )
}
