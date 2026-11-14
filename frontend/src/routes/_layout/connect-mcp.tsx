import { createFileRoute } from "@tanstack/react-router"
import { McpSetup } from "@/features/mcp-access"

// Not /mcp: Caddy and the Vite proxy send /mcp* to the backend.
export const Route = createFileRoute("/_layout/connect-mcp")({
  component: McpSetup,
  head: () => ({
    meta: [{ title: "MCP - agentique" }],
  }),
})
