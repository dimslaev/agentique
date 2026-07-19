import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  className?: string
  asLink?: boolean
  /** Expands from "ag" to "agentique" with the sidebar collapse state. */
  expandable?: boolean
  /** Always renders the full "agentique" wordmark, no collapse/hover behavior. */
  full?: boolean
}

const box =
  "inline-flex h-8 items-center justify-center font-mono font-medium lowercase text-foreground"

export function Logo({
  className,
  asLink = true,
  expandable = false,
  full = false,
}: LogoProps) {
  const content = full ? (
    <span className={cn(box, "px-2", className)}>agentique</span>
  ) : expandable ? (
    <span className={cn(box, "px-2", className)}>
      <span>ag</span>
      {/* grid-template-columns 1fr→0fr animates smoothly; the border just
          tracks the reflow, so the box grows without a width transition */}
      <span className="grid grid-cols-[1fr] transition-[grid-template-columns] duration-200 ease-out group-data-[collapsible=icon]:grid-cols-[0fr]">
        <span className="overflow-hidden whitespace-nowrap">entique</span>
      </span>
    </span>
  ) : (
    <span className={cn(box, "w-8", className)}>ag</span>
  )

  if (!asLink) return content

  return <Link to="/">{content}</Link>
}
