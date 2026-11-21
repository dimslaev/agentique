import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import { ChartColumn, LogOut, Plug, User as UserIcon } from "lucide-react"
import { useAuth } from "@/shared/auth"
import { trackEvent } from "@/shared/lib/analytics"
import { cn } from "@/shared/lib/utils"
import { Avatar, AvatarFallback } from "@/shared/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu"

const getInitials = (name: string): string =>
  name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()

// Same active treatment as the nav links (see site-header): the underline
// spans the full header height so it touches the bottom border.
const ACTIVE = "h-12 w-8 text-paper shadow-[inset_0_-2px_0_var(--signal)]"

export function UserMenu() {
  const { user, logout } = useAuth()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const active = user ? pathname === "/profile" : pathname === "/login"

  if (!user) {
    return (
      <RouterLink
        to="/login"
        data-testid="login-link"
        aria-label="Sign in"
        title="Sign in"
        aria-current={active ? "page" : undefined}
        className={cn(
          "flex items-center justify-center text-dim transition-colors hover:text-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal",
          active ? ACTIVE : "size-8",
        )}
      >
        <UserIcon className="size-[18px]" />
      </RouterLink>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Account menu"
          data-testid="user-menu"
          aria-current={active ? "page" : undefined}
          className={cn(
            "flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
            active && ACTIVE,
          )}
        >
          <Avatar className="size-8">
            <AvatarFallback className="bg-muted font-wire text-xs text-foreground">
              {user.full_name ? (
                getInitials(user.full_name)
              ) : (
                <UserIcon className="size-[18px]" />
              )}
            </AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-56" align="end" sideOffset={6}>
        <DropdownMenuLabel className="flex flex-col font-normal">
          {user.full_name && (
            <span className="truncate text-sm font-medium">
              {user.full_name}
            </span>
          )}
          <span className="truncate text-xs text-muted-foreground">
            {user.email}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <RouterLink to="/profile">
            <UserIcon />
            Profile
          </RouterLink>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <RouterLink to="/connect-mcp">
            <Plug />
            MCP
          </RouterLink>
        </DropdownMenuItem>
        {user.is_superuser && (
          <DropdownMenuItem asChild>
            <RouterLink to="/admin">
              <ChartColumn />
              Analytics
            </RouterLink>
          </DropdownMenuItem>
        )}
        <DropdownMenuItem
          onClick={() => {
            // before the token goes, so the event carries the user
            trackEvent("logout")
            logout()
          }}
        >
          <LogOut />
          Log Out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
