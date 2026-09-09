import { Moon, Sun } from "lucide-react"

import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"

export const SidebarAppearance = () => {
  const { resolvedTheme, setTheme } = useTheme()

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        tooltip="Appearance"
        data-testid="theme-button"
        onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      >
        {resolvedTheme === "dark" ? (
          <Moon className="size-4 text-muted-foreground" />
        ) : (
          <Sun className="size-4 text-muted-foreground" />
        )}
        <span>{resolvedTheme === "dark" ? "Dark" : "Light"}</span>
        <span className="sr-only">Toggle theme</span>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export const Appearance = () => {
  const { resolvedTheme, setTheme } = useTheme()

  return (
    <div className="flex items-center justify-center">
      <Button
        data-testid="theme-button"
        variant="outline"
        size="icon"
        onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      >
        {resolvedTheme === "dark" ? (
          <Moon className="h-[1.2rem] w-[1.2rem]" />
        ) : (
          <Sun className="h-[1.2rem] w-[1.2rem]" />
        )}
        <span className="sr-only">Toggle theme</span>
      </Button>
    </div>
  )
}
