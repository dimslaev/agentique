import { expect, type Page, test } from "@playwright/test"

// Wide enough that the rails sit inline beside the feed, always open.
test.use({ viewport: { width: 1440, height: 900 } })

const CLUSTERS = [
  { id: 0, label: "Coding agents", x: 0.3, y: 0.3, size: 4 },
  { id: 1, label: "Open weights", x: 0.7, y: 0.3, size: 3 },
  { id: 2, label: "Retrieval", x: 0.5, y: 0.75, size: 3 },
]

function fixture(generatedAt = new Date()) {
  const points = CLUSTERS.flatMap((c) =>
    Array.from({ length: c.size }, (_, i) => ({
      id: c.id * 100 + i,
      x: c.x + (i - 1) * 0.04,
      y: c.y + (i % 2) * 0.04,
      cluster: c.id,
      score: i === 0 ? 88 : 55,
      title: `${c.label} article ${i}`,
      url: `https://example.com/${c.id}/${i}`,
      publisher: `Publisher ${c.id}`,
    })),
  )
  return {
    v: 1,
    generated_at: generatedAt.toISOString(),
    window_days: 7,
    since: new Date(generatedAt.getTime() - 7 * 864e5).toISOString(),
    count: points.length,
    clusters: CLUSTERS,
    points,
  }
}

async function serve(page: Page, body: unknown, status = 200) {
  await page.route("/data/topic-map.json", (route) =>
    route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    }),
  )
}

test("the topic map draws a dot per article and a label per cluster", async ({
  page,
}) => {
  await serve(page, fixture())
  await page.goto("/")

  const map = page.getByTestId("topic-map")
  await expect(map).toBeVisible()
  await expect(map.getByText("this week · 10")).toBeVisible()
  await expect(map.getByTestId("topic-map-dot")).toHaveCount(10)
  for (const c of CLUSTERS) {
    await expect(
      map.getByRole("button", { name: `Highlight ${c.label}` }),
    ).toBeVisible()
  }
  await expect(map.getByRole("img")).toHaveAttribute(
    "aria-label",
    "10 articles in 3 clusters: Coding agents (4), Open weights (3), Retrieval (3)",
  )
})

test("clicking a label keeps its cluster and dims the rest", async ({
  page,
}) => {
  await serve(page, fixture())
  await page.goto("/")

  const map = page.getByTestId("topic-map")
  const label = map.getByRole("button", { name: "Highlight Retrieval" })
  await label.click()
  await expect(label).toHaveAttribute("aria-pressed", "true")
  await expect(
    map.locator('[data-testid="topic-map-dot"].opacity-15'),
  ).toHaveCount(7)
  await label.click()
  await expect(
    map.locator('[data-testid="topic-map-dot"].opacity-15'),
  ).toHaveCount(0)
})

test("a missing file hides the panel", async ({ page }) => {
  await page.route("/data/topic-map.json", (route) =>
    route.fulfill({ status: 404, body: "" }),
  )
  await page.goto("/")

  await expect(page.getByTestId("article-row").first()).toBeVisible()
  await expect(page.getByTestId("topic-map")).toHaveCount(0)
  await expect(page.locator('[data-panel="topic-map"]')).toBeHidden()
})

test("a stale file hides the panel", async ({ page }) => {
  await serve(page, fixture(new Date(Date.now() - 4 * 864e5)))
  await page.goto("/")

  await expect(page.getByTestId("article-row").first()).toBeVisible()
  await expect(page.locator('[data-panel="topic-map"]')).toBeHidden()
})
