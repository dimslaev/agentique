import { expect, test } from "@playwright/test"

test("Landing page renders topic boxes with articles", async ({ page }) => {
  await page.goto("/")

  const firstLane = page.getByTestId("topic-lane-open-source-drops")
  await expect(firstLane).toBeVisible()
  await expect(firstLane.locator("li a").first()).toBeVisible()
})

test("Boxes below the fold only load once scrolled to", async ({ page }) => {
  const requested: string[] = []
  page.on("request", (req) => {
    if (req.url().includes("/api/v1/articles")) requested.push(req.url())
  })

  await page.goto("/")
  await expect(
    page.getByTestId("topic-lane-open-source-drops").locator("li a").first(),
  ).toBeVisible()
  const onFirstPaint = requested.length

  // The last box is far below the fold, so it must still be empty here.
  const lastLane = page.getByTestId("topic-lane-google")
  await expect(lastLane).toBeAttached()
  expect(await lastLane.locator("li a").count()).toBe(0)

  await lastLane.scrollIntoViewIfNeeded()
  await expect(lastLane.locator("li a").first()).toBeVisible()

  expect(requested.length).toBeGreaterThan(onFirstPaint)
})
