import { expect, test } from "@playwright/test"

test.use({ permissions: ["clipboard-read", "clipboard-write"] })

test("the MCP page shows a config per agent and copies it", async ({
  page,
}) => {
  await page.goto("/connect-mcp")
  await expect(page.getByRole("heading", { name: "MCP" })).toBeVisible()

  await page.getByRole("tab", { name: "Codex CLI" }).click()
  await expect(page.getByText("[mcp_servers.agentique]")).toBeVisible()

  await page.getByRole("tab", { name: "VS Code" }).click()
  await page.getByRole("button", { name: "Copy .vscode/mcp.json" }).click()
  const copied = await page.evaluate(() => navigator.clipboard.readText())
  expect(JSON.parse(copied).servers.agentique.type).toBe("http")
})

test("the example prompt copies", async ({ page }) => {
  await page.goto("/connect-mcp")
  await page.getByRole("button", { name: "Copy prompt" }).click()
  const copied = await page.evaluate(() => navigator.clipboard.readText())
  expect(copied).toContain("Using the agentique MCP")
})

test("a new token fills the agent configs", async ({ page }) => {
  await page.goto("/connect-mcp")
  await page.getByRole("button", { name: /Create token|Replace token/ }).click()
  await expect(page.getByText("Copy your token now")).toBeVisible()
  await expect(page.getByText(/Bearer agq_/)).toBeVisible()
})

test("/developers redirects to the MCP page", async ({ page }) => {
  await page.goto("/developers")
  await expect(page).toHaveURL(/\/connect-mcp$/)
})
