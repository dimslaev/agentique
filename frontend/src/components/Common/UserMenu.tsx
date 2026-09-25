import { Link as RouterLink } from "@tanstack/react-router"
import { LogIn, LogOut, User as UserIcon } from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"

const getInitials = (name: string): string =>
  name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()

export function UserMenu() {
  const { user, logout } = useAuth()

  if (!user) {
    return (
      // Same outline icon button as the theme toggle beside it.
      <Button variant="outline" size="icon" asChild>
        <RouterLink to="/login" data-testid="login-link" aria-label="Sign in">
          <LogIn className="h-[1.2rem] w-[1.2rem]" />
        </RouterLink>
      </Button>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Account menu"
          data-testid="user-menu"
          className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <Avatar className="size-8">
            <AvatarFallback className="bg-muted font-wire text-xs text-foreground">
              {getInitials(user.full_name || "User")}
            </AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-56" align="end" sideOffset={6}>
        <DropdownMenuLabel className="flex flex-col font-normal">
          <span className="truncate text-sm font-medium">{user.full_name}</span>
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
        <DropdownMenuItem onClick={logout}>
          <LogOut />
          Log Out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
