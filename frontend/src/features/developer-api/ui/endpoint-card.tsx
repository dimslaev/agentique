export function EndpointCard({
  method,
  path,
  description,
  params,
}: {
  method: string
  path: string
  description: string
  params: { name: string; description: string }[]
}) {
  return (
    <div className="rounded-lg border bg-card p-5 space-y-4">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-wire text-xs font-bold text-primary">
            {method}
          </span>
          <code className="font-wire text-sm text-foreground">{path}</code>
        </div>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>

      <dl className="space-y-2">
        {params.map(({ name, description: desc }) => (
          <div key={name} className="flex gap-4 text-xs">
            <dt className="font-wire text-foreground w-28 shrink-0">{name}</dt>
            <dd className="text-muted-foreground">{desc}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
