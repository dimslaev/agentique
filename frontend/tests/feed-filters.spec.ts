import { expect, type Page, test } from "@playwright/test"

type Article = {
  title: string
  score: number
  kind: string
  published_at: string
  publisher: { kind: string }
  tags: { slug: string }[]
}

function articleRows(page: Page) {
  return page.getByTestId("article-row")
}

function option(page: Page, row: string, name: string) {
  return page
    .getByRole("group", { name: row })
    .getByRole("button", { name, exact: true })
}

/** Clicks one option in a filter row and returns the feed it asked for, once
 *  the list shows it. Only the feed asks for 50 articles; the rails ask for
 *  fewer. */
async function pick(
  page: Page,
  row: string,
  name: string,
  asks: (params: URLSearchParams) => boolean,
) {
  const response = page.waitForResponse((r) => {
    const url = new URL(r.url())
    return (
      url.pathname === "/api/v1/articles/" &&
      url.searchParams.get("limit") === "50" &&
      asks(url.searchParams)
    )
  })
  await option(page, row, name).click()
  const { data } = (await (await response).json()) as { data: Article[] }

  await expect(option(page, row, name)).toHaveAttribute("aria-pressed", "true")
  if (data.length === 0) {
    await expect(page.getByTestId("articles-empty")).toBeVisible()
  } else {
    await expect(articleRows(page)).toHaveCount(data.length)
    await expect(articleRows(page).first()).toContainText(data[0].title)
  }
  return data
}

test.beforeEach(async ({ page }) => {
  await page.goto("/")
  await expect(articleRows(page).first()).toBeVisible()
})

test("From narrows the feed to one origin, All lifts it", async ({ page }) => {
  const data = await pick(
    page,
    "From",
    "Media",
    (q) => q.get("origin") === "media",
  )
  expect(data.length).toBeGreaterThan(0)
  for (const a of data) {
    expect(a.kind).toBe("post")
    expect(["media", "community"]).toContain(a.publisher.kind)
  }

  await pick(page, "From", "All", (q) => !q.has("origin"))
  await expect(option(page, "From", "Media")).toHaveAttribute(
    "aria-pressed",
    "false",
  )
})

test("Topics narrows the feed to the topic's tags", async ({ page }) => {
  const tags = ["kimi", "deepseek", "qwen", "glm", "mistral", "meta", "nvidia"]
  const data = await pick(
    page,
    "Topics",
    "Open weights",
    (q) => q.getAll("tag").join() === tags.join(),
  )
  expect(data.length).toBeGreaterThan(0)
  for (const a of data) {
    expect(a.tags.some((t) => tags.includes(t.slug))).toBe(true)
  }
})

test("Published narrows the feed to its window", async ({ page }) => {
  const threeDaysAgo = Date.now() - 3 * 864e5
  // A minute of slack for the time between the click and the request.
  const data = await pick(page, "Published", "3 days", (q) => {
    const since = new Date(q.get("since") ?? "").getTime()
    return Math.abs(since - threeDaysAgo) < 60e3
  })
  expect(data.length).toBeGreaterThan(0)
  for (const a of data) {
    expect(new Date(a.published_at).getTime()).toBeGreaterThan(
      threeDaysAgo - 60e3,
    )
  }
})

test("Sort by orders the feed", async ({ page }) => {
  const data = await pick(
    page,
    "Sort by",
    "Score",
    (q) => q.get("sort") === "score-desc",
  )
  expect(data.length).toBeGreaterThan(1)
  const scores = data.map((a) => a.score)
  expect(scores).toEqual([...scores].sort((a, b) => b - a))
})

test("a search replaces the feed and greys out the rows it ignores", async ({
  page,
}) => {
  const found = {
    id: 1,
    title: "Running a model on a laptop",
    url: "https://example.com/local",
    summary: null,
    score: 80,
    kind: "post",
    found_via: null,
    published_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    publisher: { id: 1, slug: "someone", name: "Someone", kind: "individual" },
    tags: [],
    like_count: 0,
    liked_by_me: false,
  }
  // Search embeds the query, which needs a model the test stack doesn't run.
  await page.route(
    (url) => url.pathname === "/api/v1/articles/search",
    (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ data: [found], count: 1 }),
      }),
  )

  const searched = page.waitForRequest(
    (r) => new URL(r.url()).searchParams.get("q") === "run a model",
  )
  await page
    .getByRole("textbox", { name: "Search articles" })
    .fill("run a model")
  await searched

  await expect(articleRows(page)).toHaveCount(1)
  await expect(articleRows(page)).toContainText(found.title)
  for (const row of ["From", "Published"]) {
    await expect(
      page
        .getByRole("group", { name: row })
        .locator("xpath=ancestor::*[@inert]"),
    ).toHaveCount(1)
  }

  await page.getByRole("button", { name: "Clear search" }).click()
  await expect(page.getByText(found.title)).toHaveCount(0)
  await expect(articleRows(page).first()).toBeVisible()
})

test("filters reset when the reader leaves the feed and comes back", async ({
  page,
}) => {
  await pick(page, "From", "Media", (q) => q.get("origin") === "media")

  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Profile" }).click()
  await page.waitForURL("/profile")
  await page
    .getByRole("banner")
    .getByRole("link", { name: "Feed", exact: true })
    .click()

  await expect(option(page, "From", "All")).toHaveAttribute(
    "aria-pressed",
    "true",
  )
  await expect(option(page, "From", "Media")).toHaveAttribute(
    "aria-pressed",
    "false",
  )
})
