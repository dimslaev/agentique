import { expect, test } from "@playwright/test"

test.use({ permissions: ["clipboard-read", "clipboard-write"] })

test("the developers page lists the API and Upgrade says it's coming soon", async ({
  page,
}) => {
  await page.goto("/developers")
  await expect(page.getByRole("heading", { name: "Pro plan" })).toBeVisible()
  for (const path of ["/api/v1/articles", "/api/v1/articles/search"]) {
    await expect(page.getByText(path, { exact: true })).toBeVisible()
  }

  await page.getByRole("button", { name: /Upgrade to Pro/ }).click()
  const dialog = page.getByRole("dialog", { name: "Coming soon" })
  await expect(dialog).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(dialog).toHaveCount(0)
})

test("copy puts the response shape on the clipboard", async ({ page }) => {
  await page.goto("/developers")
  await page.getByRole("button", { name: "copy" }).click()
  await expect(page.getByRole("button", { name: "copied" })).toBeVisible()
  const copied = await page.evaluate(() => navigator.clipboard.readText())
  expect(JSON.parse(copied)).toHaveProperty("count")
})
