import { expect, test } from "@playwright/test"

test("an unknown path shows the 404 page, and Go Back returns to the feed", async ({
  page,
}) => {
  await page.goto("/no-such-page")
  await expect(page.getByTestId("not-found")).toContainText("404")

  await page.getByRole("button", { name: "Go Back" }).click()
  await page.waitForURL("/")
  await expect(page.getByTestId("article-row").first()).toBeVisible()
})
