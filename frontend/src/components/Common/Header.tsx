import { Logo } from "@/components/Common/Logo"
import { cn } from "@/lib/utils"

interface HeaderProps {
  nav?: React.ReactNode
  /** Span the feed column plus both side rails (768 + 2 × 300px) instead of
   *  the reading column, so the header's edges line up with the rails'. */
  wide?: boolean
}

// Site header shared by the feed shell and the auth pages.
export function Header({ nav, wide = false }: HeaderProps) {
  return (
    <header className="sticky top-0 z-10 shrink-0 border-b bg-background">
      <div
        className={cn(
          "mx-auto flex h-12 items-center gap-4 px-4",
          wide ? "max-w-[calc(1368px+2rem)]" : "max-w-3xl",
        )}
      >
        <Logo full className="-ml-2" />
        <div className="ml-auto flex items-center gap-3">{nav}</div>
      </div>
    </header>
  )
}
