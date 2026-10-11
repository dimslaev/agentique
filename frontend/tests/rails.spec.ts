import { expect, type Page, test } from "@playwright/test"
import { openAllPanels } from "./rails"

const RAIL = "Left rail"

function leftRail(page: Page) {
  return page.getByRole("complementary", { name: RAIL })
}

function whoWrote(page: Page) {
  return page.locator('[data-panel="who-wrote"]')
}

test.describe("wide screen", () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test("the left rail sits inline and a panel's open state survives a reload", async ({
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
    // Only Stories starts open.
    await expect(header).toHaveAttribute("aria-expanded", "false")
    await header.click()
    await expect(header).toHaveAttribute("aria-expanded", "true")
    await page.reload()
    await expect(header).toHaveAttribute("aria-expanded", "true")
    await header.click()
    await expect(header).toHaveAttribute("aria-expanded", "false")
    await page.reload()
    await expect(header).toHaveAttribute("aria-expanded", "false")
  })

  test("clicking Writers sets the From filter and the feed shows only writers", async ({
    page,
  }) => {
    await openAllPanels(page)
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

for (const [name, width, height] of [
  ["mid screen", 1000, 800],
  ["phone", 390, 844],
] as const) {
  test.describe(name, () => {
    test.use({ viewport: { width, height } })

    test("one header button opens both rails as one sheet", async ({
      page,
    }) => {
      await page.goto("/")
      await expect(leftRail(page)).toHaveCount(0)

      await expect(page.locator("[data-rail-trigger]")).toHaveCount(1)
      await page.getByRole("button", { name: "Toggle the rails" }).click()
      await expect(page.getByRole("dialog", { name: "Rails" })).toBeVisible()
      await expect(whoWrote(page)).toBeVisible()
      await expect(whoWrote(page).getByRole("button").first()).toHaveAttribute(
        "aria-expanded",
        "false",
      )

      await page.keyboard.press("Escape")
      await expect(page.getByRole("dialog", { name: "Rails" })).toHaveCount(0)
    })
  })
}
