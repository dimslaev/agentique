import { expect, type Page, test } from "@playwright/test"

// Wide enough that the rails sit inline beside the feed, always open.
test.use({ viewport: { width: 1440, height: 900 } })

function article(id: number, likeCount: number) {
  return {
    id,
    title: `Picked article ${id}`,
    url: `https://example.com/picks/${id}`,
    summary: null,
    score: 50 + id,
    kind: "post",
    found_via: null,
    published_at: new Date(Date.now() - id * 864e5).toISOString(),
    created_at: new Date().toISOString(),
    publisher: {
      id: 1,
      slug: "example",
      name: "Example",
      kind: "individual",
    },
    tags: [],
    like_count: likeCount,
    liked_by_me: false,
  }
}

// Only the panel's request: the feed's own query keeps hitting the backend.
async function servePicks(page: Page, data: ReturnType<typeof article>[]) {
  await page.route(
    (url) =>
      url.pathname === "/api/v1/articles/" &&
      url.searchParams.get("sort") === "likes-desc",
    (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ data, count: data.length }),
      }),
  )
}

test("reader picks lists liked articles with their counts, most liked first", async ({
  page,
}) => {
  // In like order, as the backend sorts them; the unliked tail is dropped.
  await servePicks(page, [
    article(1, 5),
    article(2, 3),
    article(3, 1),
    article(4, 0),
    article(5, 0),
  ])
  await page.goto("/")

  const rows = page.getByTestId("reader-pick")
  await expect(rows).toHaveCount(3)
  await expect(rows.getByRole("link")).toHaveText([
    "Picked article 1",
    "Picked article 2",
    "Picked article 3",
  ])
  await expect(rows.getByTestId("like-count")).toHaveText(["5", "3", "1"])
  await expect(rows.first().getByRole("link")).toHaveAttribute(
    "target",
    "_blank",
  )
  await expect(rows.first()).toContainText(/Example · \w{3} \d+/i)
})

test("with no liked articles the panel is hidden", async ({ page }) => {
  await servePicks(page, [article(1, 0), article(2, 0)])
  await page.goto("/")

  await expect(page.getByTestId("article-row").first()).toBeVisible()
  await expect(page.getByTestId("reader-picks")).toHaveCount(0)
  await expect(page.locator('[data-panel="reader-picks"]')).toBeHidden()
})

test("a like in the feed shows in the panel, and an unlike in the panel shows in the feed", async ({
  page,
}) => {
  await page.goto("/")
  // Not the first row: likes.spec toggles that one and may run alongside.
  const feedRow = page.getByTestId("article-row").nth(2)
  const title = await feedRow.locator("a").first().textContent()
  const feedLike = feedRow.getByTestId("like-button")
  const feedCount = feedRow.getByTestId("like-count")

  const startLiked = (await feedLike.getAttribute("data-liked")) === "true"
  if (!startLiked) {
    const before = Number(await feedCount.textContent())
    await feedLike.click()
    await expect(feedCount).toHaveText(String(before + 1))
  }
  const liked = Number(await feedCount.textContent())

  const pick = page
    .getByTestId("reader-pick")
    .filter({ has: page.getByRole("link", { name: title ?? "", exact: true }) })
  await expect(pick.getByTestId("like-count")).toHaveText(String(liked))
  await expect(pick.getByTestId("like-button")).toHaveAttribute(
    "data-liked",
    "true",
  )

  await pick.getByTestId("like-button").click()
  await expect(feedCount).toHaveText(String(liked - 1))
  await expect(feedLike).toHaveAttribute("data-liked", "false")

  // Leave the article as it was found.
  if (startLiked) {
    await feedLike.click()
    await expect(feedLike).toHaveAttribute("data-liked", "true")
  }
})

test.describe("logged out", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("liking in the panel sends you to login", async ({ page }) => {
    await servePicks(page, [article(1, 2)])
    await page.goto("/")

    await page.getByTestId("reader-pick").getByTestId("like-button").click()
    await page.waitForURL(/\/login/)
  })
})
