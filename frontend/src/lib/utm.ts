export function utmSource(): string | undefined {
  return (
    new URLSearchParams(window.location.search).get("utm_source") ?? undefined
  )
}
