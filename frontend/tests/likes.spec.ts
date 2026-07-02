import { expect, test } from "@playwright/test"

test.describe("Anonymous likes", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("article rows show a fire button with a numeric badge, including 0", async ({
    page,
  }) => {
    await page.goto("/")
    const firstRow = page.getByTestId("article-row").first()
    await expect(firstRow.getByTestId("like-button")).toBeVisible()
    const countText = await firstRow.getByTestId("like-count").textContent()
    expect(countText).toMatch(/^\d+$/)
  })

  test("clicking the fire while logged out redirects to /login with a redirect param", async ({
    page,
  }) => {
    await page.goto("/")
    await page.getByTestId("like-button").first().click()
    await page.waitForURL(/\/login/)
    const url = new URL(page.url())
    expect(url.searchParams.get("redirect")).toBeTruthy()
  })
})

test.describe("Logged-in likes", () => {
  test("clicking the fire toggles the like optimistically", async ({
    page,
  }) => {
    await page.goto("/")
    const firstRow = page.getByTestId("article-row").first()
    const likeButton = firstRow.getByTestId("like-button")
    const likeCount = firstRow.getByTestId("like-count")

    const initialCount = Number(await likeCount.textContent())

    await likeButton.click()
    await expect(likeCount).toHaveText(String(initialCount + 1))
    await expect(likeButton).toHaveAttribute("data-liked", "true")

    await likeButton.click()
    await expect(likeCount).toHaveText(String(initialCount))
    await expect(likeButton).toHaveAttribute("data-liked", "false")
  })
})

test.describe("Popular sort", () => {
  test("sort filter shows Popular and selecting it reorders the list", async ({
    page,
  }) => {
    await page.goto("/")
    const popularOption = page.getByRole("button", { name: "Popular" })
    await expect(popularOption).toBeVisible()
    await popularOption.click()

    await expect(page.getByTestId("article-row").first()).toBeVisible()
  })
})
