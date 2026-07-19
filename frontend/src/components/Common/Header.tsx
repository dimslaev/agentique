import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"

interface HeaderProps {
  nav?: React.ReactNode
}

export function Header({ nav }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b px-6 py-3">
      <Logo full />
      <nav className="flex items-center gap-1">
        {nav}
        <Appearance />
      </nav>
    </header>
  )
}
