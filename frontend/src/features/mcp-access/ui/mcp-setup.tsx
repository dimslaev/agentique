import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { type ReactNode, useState } from "react"
import { UsersService } from "@/shared/api"
import { isLoggedIn } from "@/shared/auth"
import { handleError } from "@/shared/lib/api-error"
import useCustomToast from "@/shared/lib/use-custom-toast"
import { Button } from "@/shared/ui/button"
import { LoadingButton } from "@/shared/ui/loading-button"
import { AgentExamples } from "./agent-examples"
import { CodeBlock } from "./code-block"

const MCP_URL = `${import.meta.env.VITE_API_URL}/mcp/`
const QUERY_KEY = ["mcpToken"]
const TOKEN_PLACEHOLDER = "YOUR_TOKEN"

const EXAMPLE_PROMPT =
  "Using the agentique MCP (search, tags and sql_query together), find the most practical ways to sandbox local AI coding agents that work today. Use engineering blogs and individual writers, not vendor marketing. Refine your own queries until coverage is good, without asking me anything. Return one ranked list: link, one-line takeaway, and what to do on a dev machine."

const TOOLS = [
  {
    name: "tags",
    description: "Every tag, with the number of articles that carry it.",
  },
  {
    name: "search",
    description:
      "Articles by keyword and by meaning, filtered by tag, kind, date or publisher. Returns links and excerpts, at most 100 results.",
  },
  {
    name: "sql_query",
    description:
      "Read-only SQL over article, publisher, tag and article_tag. Cancels a statement after 3 seconds and returns at most 1000 rows.",
  },
]

function Step({
  number,
  title,
  children,
}: {
  number?: number
  title: string
  children: ReactNode
}) {
  return (
    <section className="space-y-4">
      <h2 className="flex items-baseline gap-3 font-display text-lg font-bold tracking-tight">
        {number && (
          <span className="font-wire text-xs font-normal text-primary">
            {number}
          </span>
        )}
        {title}
      </h2>
      {children}
    </section>
  )
}

/** The MCP page: make a token, connect an agent, try a prompt. The token is
 *  held in state only, so it is gone once the page is left. */
export function McpSetup() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [token, setToken] = useState<string | null>(null)
  const signedIn = isLoggedIn()

  const { data: status, isError } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: UsersService.readMcpToken,
    enabled: signedIn,
  })

  const create = useMutation({
    mutationFn: UsersService.createMcpToken,
    onSuccess: (created) => setToken(created.token),
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })

  const revoke = useMutation({
    mutationFn: UsersService.revokeMcpToken,
    onSuccess: () => {
      setToken(null)
      showSuccessToast("MCP token revoked")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: QUERY_KEY }),
  })

  return (
    <div className="space-y-10">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight">MCP</h1>
        <p className="mt-2 text-muted-foreground">
          Search the agentique archive from your coding agent. Free with an
          account.
        </p>
      </div>

      <Step number={1} title="Get a token">
        {!signedIn && (
          <Button asChild>
            <Link to="/login" search={{ redirect: "/connect" }}>
              Sign up for MCP access
            </Link>
          </Button>
        )}

        {isError && (
          <p className="text-sm text-destructive">
            Your token didn&apos;t load. Reload the page.
          </p>
        )}

        {signedIn && token && (
          <>
            <p className="text-sm text-muted-foreground">
              Copy your token now. It won&apos;t be shown again. The examples
              below already include it.
            </p>
            <CodeBlock label="token" code={token} />
          </>
        )}

        {signedIn && !token && status?.exists && (
          <p className="text-sm text-muted-foreground">
            You have a token
            {status.created_at &&
              `, created ${new Date(status.created_at).toLocaleDateString()}`}
            . It can&apos;t be shown again. Replacing it stops the old one
            working.
          </p>
        )}

        {signedIn && status && (
          <div className="flex gap-3">
            <LoadingButton
              variant={token ? "outline" : "default"}
              loading={create.isPending}
              onClick={() => create.mutate()}
            >
              {status.exists ? "Replace token" : "Create token"}
            </LoadingButton>
            {status.exists && (
              <LoadingButton
                variant="outline"
                loading={revoke.isPending}
                onClick={() => revoke.mutate()}
              >
                Revoke
              </LoadingButton>
            )}
          </div>
        )}
      </Step>

      <Step number={2} title="Add it to your agent">
        <AgentExamples url={MCP_URL} token={token ?? TOKEN_PLACEHOLDER} />
        <p className="text-sm text-muted-foreground">
          Any other client: HTTP transport at{" "}
          <code className="font-wire text-xs text-foreground">{MCP_URL}</code>{" "}
          with the header{" "}
          <code className="font-wire text-xs text-foreground">
            Authorization: Bearer {TOKEN_PLACEHOLDER}
          </code>
          .
        </p>
      </Step>

      <Step number={3} title="Try a prompt">
        <CodeBlock label="prompt" code={EXAMPLE_PROMPT} prose />
      </Step>

      <Step title="Tools">
        <dl className="space-y-3">
          {TOOLS.map(({ name, description }) => (
            <div key={name} className="gap-4 text-sm sm:flex">
              <dt className="w-24 shrink-0 font-wire text-xs leading-5 text-foreground">
                {name}
              </dt>
              <dd className="text-muted-foreground">{description}</dd>
            </div>
          ))}
        </dl>
      </Step>

      <Step title="Rate limits">
        <p className="text-sm text-muted-foreground">
          Up to 20 tool calls a minute and 500 a day per account, counted across
          all three tools. Over the limit, the tool returns an error that says
          how many seconds to wait.
        </p>
      </Step>
    </div>
  )
}
