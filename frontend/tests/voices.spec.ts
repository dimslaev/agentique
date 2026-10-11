import { expect, type Page, test } from "@playwright/test"
import { openAllPanels } from "./rails"

// Wide enough that the rails sit inline beside the feed, always open.
test.use({ viewport: { width: 1440, height: 900 } })

test.beforeEach(({ page }) => openAllPanels(page))

function voice(slug: string, name: string, count: number) {
  return {
    slug,
    name,
    count,
    scores: Array.from({ length: count }, (_, i) => 60 + i * 5),
    best: {
      title: `Best of ${name}`,
      url: `https://example.com/${slug}`,
      score: 85,
      published_at: new Date().toISOString(),
    },
  }
}

const VOICES: Record<string, ReturnType<typeof voice>[]> = {
  individual: [
    voice("simon-willison", "Simon Willison", 5),
    voice("hamel-husain", "Hamel Husain", 2),
  ],
  lab: [voice("anthropic", "Anthropic", 4)],
  company: [],
}

function article(id: number) {
  return {
    id,
    title: `Article by Simon ${id}`,
    url: `https://example.com/simon/${id}`,
    summary: null,
    score: 70,
    kind: "post",
    found_via: null,
    published_at: new Date(Date.now() - id * 864e5).toISOString(),
    created_at: new Date().toISOString(),
    publisher: {
      id: 1,
      slug: "simon-willison",
      name: "Simon Willison",
      kind: "individual",
    },
    tags: [],
    like_count: 0,
    liked_by_me: false,
  }
}

async function serveVoices(page: Page) {
  await page.route(
    (url) => url.pathname === "/api/v1/articles/voices",
    (route) => {
      const kind = new URL(route.request().url()).searchParams.get("kind")
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(VOICES[kind ?? ""] ?? []),
      })
    },
  )
}

// Only the feed's request for this publisher; everything else hits the backend.
async function servePublisherFeed(page: Page) {
  const data = [article(1), article(2)]
  await page.route(
    (url) =>
      url.pathname === "/api/v1/articles/" &&
      url.searchParams.get("publisher") === "simon-willison",
    (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ data, count: data.length }),
      }),
  )
}

function panel(page: Page) {
  return page.locator('[data-panel="voices"]')
}

test("tabs switch the list", async ({ page }) => {
  await serveVoices(page)
  await page.goto("/")
  const tabs = panel(page).getByRole("group", { name: "Voices" })
  const names = panel(page).getByTestId("voice-name")

  await expect(tabs.getByRole("button", { name: "Writers" })).toHaveAttribute(
    "aria-pressed",
    "true",
  )
  await expect(names).toHaveText(["Simon Willison", "Hamel Husain"])
  await expect(panel(page).getByTestId("voice").first()).toContainText(
    "Best of Simon Willison",
  )

  await tabs.getByRole("button", { name: "Labs" }).click()
  await expect(names).toHaveText(["Anthropic"])

  await tabs.getByRole("button", { name: "Companies" }).click()
  await expect(names).toHaveCount(0)
  await expect(panel(page)).toContainText("Nobody here")
})

test("clicking a name narrows the feed to that publisher, and the chip clears it", async ({
  page,
}) => {
  await serveVoices(page)
  await servePublisherFeed(page)
  await page.goto("/")
  await expect(page.getByTestId("article-row").first()).toBeVisible()

  const row = panel(page)
    .getByTestId("voice")
    .filter({ hasText: "Simon Willison" })
  const narrowed = page.waitForRequest(
    (r) =>
      r.url().includes("/api/v1/articles/?") &&
      r.url().includes("publisher=simon-willison"),
  )
  await row.click()
  await narrowed

  await expect(row).toHaveAttribute("aria-pressed", "true")
  // A writer's count is posts only, so the feed narrows to Writers too.
  await expect(
    page
      .getByRole("group", { name: "From" })
      .getByRole("button", { name: "Writers" }),
  ).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByTestId("article-row")).toHaveCount(2)
  await expect(page.getByTestId("article-row").first()).toContainText(
    "Article by Simon 1",
  )
  const chip = page.getByTestId("publisher-chip")
  await expect(chip).toHaveText(/Publisher:\s*Simon Willison/)

  await chip.click()
  await expect(chip).toHaveCount(0)
  await expect(row).toHaveAttribute("aria-pressed", "false")
  await expect(page.getByText("Article by Simon 1")).toHaveCount(0)
})

test("clicking the active name clears the filter", async ({ page }) => {
  await serveVoices(page)
  await servePublisherFeed(page)
  await page.goto("/")

  const row = panel(page)
    .getByTestId("voice")
    .filter({ hasText: "Simon Willison" })
  await row.click()
  await expect(page.getByTestId("publisher-chip")).toBeVisible()

  await row.click()
  await expect(page.getByTestId("publisher-chip")).toHaveCount(0)
  await expect(row).toHaveAttribute("aria-pressed", "false")
})

test("a failed fetch hides the panel", async ({ page }) => {
  await page.route(
    (url) => url.pathname === "/api/v1/articles/voices",
    (route) => route.fulfill({ status: 500, body: "{}" }),
  )
  await page.goto("/")
  await expect(page.getByTestId("article-row").first()).toBeVisible()
  await expect(panel(page)).toBeHidden()
})
