import { cn } from "@/lib/utils"

export function FilterSectionLabel({ children }: { children: string }) {
  return (
    <p className="px-2 pb-0.5 text-[10px] uppercase tracking-wider text-muted-foreground/70">
      {children}
    </p>
  )
}

export function FilterOptionButton({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex shrink-0 items-center gap-2.5 rounded-sm px-2 py-[3px] text-xs transition-colors whitespace-nowrap",
        active
          ? "text-foreground"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      <span
        className={cn(
          "h-[5px] w-[5px] shrink-0 rounded-full transition-colors",
          active ? "bg-foreground" : "border border-muted-foreground/40",
        )}
      />
      {label}
    </button>
  )
}
