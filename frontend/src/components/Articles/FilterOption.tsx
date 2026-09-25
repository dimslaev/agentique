import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export type Option = { value: string; label: string }

export function FilterOption({
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
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        // Taller on phones so each option is a comfortable tap target.
        "whitespace-nowrap px-1.5 py-1 text-[13px] leading-4 transition-colors max-sm:px-2 max-sm:py-2",
        active
          ? "font-medium text-foreground underline decoration-1 underline-offset-[5px]"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  )
}

export function FilterOptions({
  label,
  options,
  value,
  onChange,
  children,
}: {
  label: string
  options: Option[]
  value: string
  onChange: (value: string) => void
  children?: ReactNode
}) {
  return (
    // biome-ignore lint/a11y/useSemanticElements: a fieldset's default styling fights the flex row
    <div role="group" aria-label={label} className="flex flex-wrap gap-0.5">
      {options.map((o) => (
        <FilterOption
          key={o.value}
          label={o.label}
          active={o.value === value}
          onClick={() => onChange(o.value)}
        />
      ))}
      {children}
    </div>
  )
}

/** A labelled filter row. The label keeps its own column so options that wrap
 *  onto a second line stay aligned under the first option, not the label. */
export function FilterRow({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="grid grid-cols-[72px_1fr] items-start gap-x-2 max-sm:grid-cols-[64px_1fr] max-sm:gap-x-1">
      <span className="font-wire text-[10px] uppercase leading-6 tracking-[0.1em] text-muted-foreground max-sm:pt-1">
        {label}
      </span>
      {children}
    </div>
  )
}
