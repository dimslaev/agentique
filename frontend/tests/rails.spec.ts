import { expect, type Page, test } from "@playwright/test"

const RAIL = "People and topics"

function leftRail(page: Page) {
  return page.getByRole("complementary", { name: RAIL })
}

function whoWrote(page: Page) {
  return page.locator('[data-panel="who-wrote"]')
}

test.describe("wide screen", () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test("the left rail sits inline and a folded panel stays folded after a reload", async ({
    page,
  }) => {
    await page.goto("/")
    await expect(leftRail(page)).toBeVisible()

    // Wide rails are always open: the key that toggles them on smaller
    // screens does nothing here.
    await page.keyboard.press("[")
    await expect(leftRail(page)).toBeVisible()

    const header = whoWrote(page).getByRole("button", {
      name: "Who wrote the wire",
    })
    await header.click()
    await expect(header).toHaveAttribute("aria-expanded", "false")
    await page.reload()
    await expect(header).toHaveAttribute("aria-expanded", "false")
    await header.click()
    await expect(header).toHaveAttribute("aria-expanded", "true")
    await page.reload()
    await expect(header).toHaveAttribute("aria-expanded", "true")
  })

  test("clicking Writers sets the From filter and the feed shows only writers", async ({
    page,
  }) => {
    await page.goto("/")
    const writers = whoWrote(page).getByRole("button", { name: /^Writers/ })
    await expect(writers).toBeVisible()

    const feed = page.waitForResponse(
      (r) =>
        r.url().includes("/api/v1/articles/?") &&
        r.url().includes("origin=individual"),
    )
    await writers.click()
    const { data } = await (await feed).json()

    await expect(writers).toHaveAttribute("aria-pressed", "true")
    await expect(
      page
        .getByRole("group", { name: "From" })
        .getByRole("button", { name: "Writers" }),
    ).toHaveAttribute("aria-pressed", "true")

    expect(data.length).toBeGreaterThan(0)
    for (const a of data) {
      expect(a.kind).toBe("post")
      expect(a.publisher.kind).toBe("individual")
    }
    await expect(page.getByTestId("article-row")).toHaveCount(data.length)

    // Clicking the active row clears the filter.
    await writers.click()
    await expect(writers).toHaveAttribute("aria-pressed", "false")
    await expect(
      page.getByRole("group", { name: "From" }).getByRole("button", {
        name: "All",
      }),
    ).toHaveAttribute("aria-pressed", "true")
  })
})

test.describe("mid screen", () => {
  test.use({ viewport: { width: 1000, height: 800 } })

  test("the edge strip opens an overlay and Esc closes it", async ({
    page,
  }) => {
    await page.goto("/")
    await expect(leftRail(page)).toHaveCount(0)

    await page
      .getByRole("navigation", { name: `${RAIL} rail, collapsed` })
      .getByRole("button", { name: "Who wrote the wire" })
      .click()
    await expect(leftRail(page)).toBeVisible()
    await expect(whoWrote(page).getByText(/^Of \d+:/)).toBeVisible()

    await page.keyboard.press("Escape")
    await expect(leftRail(page)).toHaveCount(0)
  })
})

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test("one header button opens both rails as one sheet", async ({ page }) => {
    await page.goto("/")
    await expect(leftRail(page)).toHaveCount(0)

    const toggles = page.locator("[data-rail-trigger]")
    await expect(toggles).toHaveCount(1)
    await page.getByRole("button", { name: "Toggle the explore rail" }).click()
    await expect(page.getByRole("dialog", { name: "Explore" })).toBeVisible()
    await expect(whoWrote(page)).toBeVisible()
  })
})
