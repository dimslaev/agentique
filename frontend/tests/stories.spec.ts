import { expect, type Page, test } from "@playwright/test"

// Wide enough that the rails sit inline beside the feed, always open.
test.use({ viewport: { width: 1440, height: 900 } })

function article(id: number, daysAgo: number, score: number) {
  return {
    id,
    title: `Article ${id}`,
    url: `https://example.com/${id}`,
    publisher: id % 2 ? "Cloudflare" : "Simon Willison",
    published_at: new Date(Date.now() - daysAgo * 86_400_000).toISOString(),
    score,
  }
}

function story(slug: string, name: string, count: number, grewToday = false) {
  const articles = Array.from({ length: count }, (_, i) =>
    article(slug.length * 100 + i, i, 40 + ((i * 17) % 60)),
  )
  return {
    slug,
    name,
    blurb: `What ${name} is. Why it matters now.`,
    article_count: count,
    publisher_count: 2,
    first_at: articles[articles.length - 1].published_at,
    last_at: articles[0].published_at,
    grew_today: grewToday,
    articles,
  }
}

const STORIES = [
  story("codemode", "Codemode", 9, true),
  story("decision-models", "Decision models", 4),
  story("local-inference", "Local inference", 3),
]

async function mockStories(page: Page, body: unknown, status = 200) {
  await page.route("**/api/v1/stories/**", (route) =>
    route.fulfill({ status, json: body }),
  )
}

/** The body that directly follows a story's row button. */
async function bodyAfter(page: Page, name: string) {
  return page
    .getByRole("button", { name })
    .evaluate((row) => row.nextElementSibling?.getAttribute("data-testid"))
}

test("the first story is open, its body right under its row", async ({
  page,
}) => {
  await mockStories(page, STORIES)
  await page.goto("/")

  const rows = page.getByTestId("story-row")
  await expect(rows).toHaveCount(3)
  await expect(rows.nth(0)).toHaveAttribute("aria-expanded", "true")
  await expect(rows.nth(1)).toHaveAttribute("aria-expanded", "false")

  expect(await bodyAfter(page, "Codemode")).toBe("story-body")
  const open = page.locator('[data-testid="story-body"][data-open="true"]')
  await expect(open).toHaveCount(1)
  await expect(open).toContainText("What Codemode is.")
  await expect(open.getByRole("link")).toHaveCount(6)
})

test("clicking another row moves the open body to it", async ({ page }) => {
  await mockStories(page, STORIES)
  await page.goto("/")

  await page.getByRole("button", { name: "Decision models" }).click()

  const rows = page.getByTestId("story-row")
  await expect(rows.nth(0)).toHaveAttribute("aria-expanded", "false")
  await expect(rows.nth(1)).toHaveAttribute("aria-expanded", "true")
  const open = page.locator('[data-testid="story-body"][data-open="true"]')
  await expect(open).toHaveCount(1)
  await expect(open).toContainText("What Decision models is.")
  // The open body sits between its row and the next story, not below the list.
  const openBodyFollowsRow = await rows
    .nth(1)
    .evaluate(
      (row) => row.nextElementSibling?.getAttribute("data-open") === "true",
    )
  expect(openBodyFollowsRow).toBe(true)
  const third = await rows.nth(2).boundingBox()
  const body = await open.boundingBox()
  expect(body && third && body.y < third.y).toBe(true)
})

test("Show all expands the timeline in place", async ({ page }) => {
  await mockStories(page, STORIES)
  await page.goto("/")

  const open = page.locator('[data-testid="story-body"][data-open="true"]')
  await expect(open.getByRole("link")).toHaveCount(6)
  await open.getByRole("button", { name: "Show all 9" }).click()
  await expect(open.getByRole("link")).toHaveCount(9)
  await expect(open.getByRole("button", { name: /Show all/ })).toHaveCount(0)
  expect(await bodyAfter(page, "Codemode")).toBe("story-body")
})

test("no stories hides the right rail", async ({ page }) => {
  await mockStories(page, [])
  await page.goto("/")

  await expect(page.getByTestId("article-row").first()).toBeVisible()
  await expect(page.locator('[data-rail="right"]')).toHaveCount(0)
})

test("a failed fetch hides the right rail", async ({ page }) => {
  await mockStories(page, { detail: "boom" }, 500)
  await page.goto("/")

  await expect(page.getByTestId("article-row").first()).toBeVisible()
  await expect(page.locator('[data-rail="right"]')).toHaveCount(0)
})
