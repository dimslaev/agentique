import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  className?: string
  asLink?: boolean
  /** Always renders the full "agentique" wordmark, no collapse/hover behavior. */
  full?: boolean
}

const box =
  "inline-flex h-8 items-center justify-center font-display font-extrabold lowercase tracking-[-0.01em] text-foreground"

export function Logo({ className, asLink = true, full = false }: LogoProps) {
  const content = full ? (
    <span className={cn(box, "px-2", className)}>agentique</span>
  ) : (
    <span className={cn(box, "w-8", className)}>ag</span>
  )

  if (!asLink) return content

  return <Link to="/">{content}</Link>
}
