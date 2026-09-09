import { useRouterState } from "@tanstack/react-router"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { SidebarFilters } from "./Filters"
import { User } from "./User"

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const router = useRouterState()
  const isHome = router.location.pathname === "/feed"

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-2 mb-2 max-md:hidden">
        <Logo expandable />
      </SidebarHeader>
      <SidebarContent className="overflow-x-hidden max-md:pt-4">
        {isHome && (
          <div className="w-[var(--sidebar-width)] shrink-0 overflow-hidden px-2 py-2 opacity-100 transition-opacity group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:opacity-0">
            <SidebarFilters />
          </div>
        )}
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
