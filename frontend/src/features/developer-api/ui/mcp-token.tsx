import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { UsersService } from "@/shared/api"
import { isLoggedIn } from "@/shared/auth"
import { handleError } from "@/shared/lib/api-error"
import useCustomToast from "@/shared/lib/use-custom-toast"
import { Button } from "@/shared/ui/button"
import { LoadingButton } from "@/shared/ui/loading-button"
import { CodeBlock } from "./code-block"

const MCP_URL = `${import.meta.env.VITE_API_URL}/mcp/`
const QUERY_KEY = ["mcpToken"]

const claudeCodeCommand = (token: string) =>
  `claude mcp add --transport http agentique ${MCP_URL} \\
  --header "Authorization: Bearer ${token}"`

/** Create, copy and revoke the signed-in reader's MCP token. The token is
 *  held in state only, so it is gone once the page is left. */
export function McpToken() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [token, setToken] = useState<string | null>(null)
  const signedIn = isLoggedIn()

  const { data: status } = useQuery({
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
    <div className="space-y-4">
      <div>
        <h2 className="font-display text-xl font-bold tracking-tight">MCP</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Connect your agent to agentique over MCP with a personal token. Free
          with an account.
        </p>
      </div>

      {!signedIn && (
        <Button asChild>
          <Link to="/login" search={{ redirect: "/developers" }}>
            Sign in to create a token
          </Link>
        </Button>
      )}

      {signedIn && token && (
        <div className="space-y-3">
          <p className="text-sm text-foreground">
            Copy your token now. It won&apos;t be shown again.
          </p>
          <CodeBlock code={token} />
          <p className="text-sm text-muted-foreground">
            Add it to Claude Code:
          </p>
          <CodeBlock code={claudeCodeCommand(token)} />
        </div>
      )}

      {signedIn && !token && status?.exists && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            You have a token
            {status.created_at &&
              `, created ${new Date(status.created_at).toLocaleDateString()}`}
            . It can&apos;t be shown again. Create a new one to replace it.
          </p>
          <CodeBlock code={claudeCodeCommand("<your token>")} />
        </div>
      )}

      {signedIn && status && (
        <div className="flex gap-3">
          <LoadingButton
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
    </div>
  )
}
