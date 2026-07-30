import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

export type Item = {
  index: string
  title: string
  path: string
  /** Rendered as a plain <a> — for pages outside the SPA (prerendered blog). */
  external?: boolean
}

interface MainProps {
  items: Item[]
}

function ItemLabel({ item, isActive }: { item: Item; isActive: boolean }) {
  return (
    <>
      <span
        className={cn(
          "flex h-[18px] w-[18px] shrink-0 items-center justify-center border font-wire text-[10px] leading-none tabular-nums transition-colors duration-200",
          isActive
            ? "border-foreground bg-foreground text-background"
            : "border-border/60 text-muted-foreground group-hover/menu-button:border-foreground group-hover/menu-button:text-foreground",
        )}
      >
        {item.index}
      </span>
      <span>{item.title}</span>
    </>
  )
}

export function Main({ items }: MainProps) {
  const { isMobile, setOpenMobile } = useSidebar()
  const router = useRouterState()
  const currentPath = router.location.pathname

  const handleMenuClick = () => {
    if (isMobile) setOpenMobile(false)
  }

  return (
    <SidebarGroup>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => {
            const isActive = currentPath === item.path

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  tooltip={item.title}
                  isActive={isActive}
                  asChild
                >
                  {item.external ? (
                    <a href={item.path} onClick={handleMenuClick}>
                      <ItemLabel item={item} isActive={isActive} />
                    </a>
                  ) : (
                    <RouterLink to={item.path} onClick={handleMenuClick}>
                      <ItemLabel item={item} isActive={isActive} />
                    </RouterLink>
                  )}
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
