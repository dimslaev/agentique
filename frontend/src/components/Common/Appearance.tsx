import { Moon, Sun } from "lucide-react"

import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"

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
