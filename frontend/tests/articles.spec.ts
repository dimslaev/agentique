import { expect, test } from "@playwright/test"

test("Articles feed renders seeded articles", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByTestId("articles-empty")).not.toBeVisible()
  await expect(page.getByTestId("article-row").first()).toBeVisible()

  const count = await page.getByTestId("article-row").count()
  expect(count).toBeGreaterThan(0)
})
