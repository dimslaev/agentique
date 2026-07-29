import { expect, test } from "@playwright/test"

// Lane slugs are category slugs now, and the lane list comes from the server
// vocabulary (`app/data/categories.json`, seeded into the `category` table) in
// `position` order. `model-releases` is position 1, `security-safety` is last.
const FIRST_LANE = "topic-lane-model-releases"
const LAST_LANE = "topic-lane-security-safety"

test("Landing page renders topic lanes with articles", async ({ page }) => {
  await page.goto("/")

  const firstLane = page.getByTestId(FIRST_LANE)
  await expect(firstLane).toBeVisible()
  await expect(firstLane.locator("li a").first()).toBeVisible()
})

test("A lane in view is exactly one request", async ({ page }) => {
  const requested: string[] = []
  page.on("request", (req) => {
    if (req.url().includes("/api/v1/articles/?")) requested.push(req.url())
  })

  await page.goto("/")
  await expect(
    page.getByTestId(FIRST_LANE).locator("li a").first(),
  ).toBeVisible()

  // The old fan-out issued up to six requests per lane and merged them
  // client-side. A lane is a single `category` filter now, so every request
  // here must carry one.
  expect(requested.length).toBeGreaterThan(0)
  for (const url of requested) {
    expect(url).toContain("category=")
  }
  expect(requested.some((url) => url.includes("category=model-releases"))).toBe(
    true,
  )
})

test("Lanes below the fold only load once scrolled to", async ({ page }) => {
  const requested: string[] = []
  page.on("request", (req) => {
    if (req.url().includes("/api/v1/articles/?")) requested.push(req.url())
  })

  await page.goto("/")
  await expect(
    page.getByTestId(FIRST_LANE).locator("li a").first(),
  ).toBeVisible()
  const onFirstPaint = requested.length

  const lastLane = page.getByTestId(LAST_LANE)
  await expect(lastLane).toBeAttached()
  expect(await lastLane.locator("li a").count()).toBe(0)

  await lastLane.scrollIntoViewIfNeeded()
  await expect(lastLane.locator("li a").first()).toBeVisible()

  expect(requested.length).toBeGreaterThan(onFirstPaint)
})
