/** How each coding agent is pointed at the MCP endpoint. Every format here
 *  was checked against that agent's own docs; recheck before adding one. */
export type Agent = {
  id: string
  name: string
  /** The file the snippet goes in, or what to do with it. */
  where: string
  /** The code block's label: a file name, or "terminal" for a command. */
  label: string
  snippet: (url: string, token: string) => string
}

const json = (value: unknown) => JSON.stringify(value, null, 2)
const bearer = (token: string) => `Bearer ${token}`

export const AGENTS: Agent[] = [
  {
    id: "claude-code",
    name: "Claude Code",
    where: "Run this in your project.",
    label: "terminal",
    snippet: (url, token) =>
      `claude mcp add --transport http agentique ${url} \\
  --header "Authorization: ${bearer(token)}"`,
  },
  {
    id: "opencode",
    name: "OpenCode",
    where:
      "Add to opencode.json in your project, or ~/.config/opencode/opencode.json for every project.",
    label: "opencode.json",
    snippet: (url, token) =>
      json({
        $schema: "https://opencode.ai/config.json",
        mcp: {
          agentique: {
            type: "remote",
            url,
            enabled: true,
            headers: { Authorization: bearer(token) },
          },
        },
      }),
  },
  {
    id: "cursor",
    name: "Cursor",
    where:
      "Add to .cursor/mcp.json in your project, or ~/.cursor/mcp.json for every project.",
    label: ".cursor/mcp.json",
    snippet: (url, token) =>
      json({
        mcpServers: {
          agentique: { url, headers: { Authorization: bearer(token) } },
        },
      }),
  },
  {
    id: "codex",
    name: "Codex CLI",
    where: "Add to ~/.codex/config.toml.",
    label: "~/.codex/config.toml",
    snippet: (url, token) =>
      `[mcp_servers.agentique]
url = "${url}"
http_headers = { "Authorization" = "${bearer(token)}" }`,
  },
  {
    id: "vscode",
    name: "VS Code",
    where:
      "Add to .vscode/mcp.json in your workspace, or run MCP: Open User Configuration for every workspace.",
    label: ".vscode/mcp.json",
    snippet: (url, token) =>
      json({
        servers: {
          agentique: {
            type: "http",
            url,
            headers: { Authorization: bearer(token) },
          },
        },
      }),
  },
]
