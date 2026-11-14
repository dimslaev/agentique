import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs"
import { AGENTS } from "../config/agents"
import { CodeBlock } from "./code-block"

/** One tab per coding agent, each with the config that connects it. */
export function AgentExamples({ url, token }: { url: string; token: string }) {
  return (
    <Tabs defaultValue={AGENTS[0].id} className="gap-4">
      <div className="overflow-x-auto">
        <TabsList className="w-max min-w-full gap-3 sm:gap-5">
          {AGENTS.map(({ id, name }) => (
            <TabsTrigger
              key={id}
              value={id}
              className="whitespace-nowrap max-sm:text-[11px] max-sm:tracking-[0.04em]"
            >
              {name}
            </TabsTrigger>
          ))}
        </TabsList>
      </div>
      {AGENTS.map(({ id, where, label, snippet }) => (
        <TabsContent key={id} value={id} className="space-y-3">
          <p className="text-sm text-muted-foreground">{where}</p>
          <CodeBlock label={label} code={snippet(url, token)} />
        </TabsContent>
      ))}
    </Tabs>
  )
}
