import { expect, test } from "@playwright/test"
import { createUser } from "./api.ts"
import { randomEmail } from "./random"
import { logInUser } from "./user"

// The setup project signs in as the first superuser.
test("an admin opens analytics from the user menu and changes the window", async ({
  page,
}) => {
  await page.goto("/")
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Analytics" }).click()
  await page.waitForURL("/admin")

  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible()
  const report = page.getByTestId("analytics-report")
  await expect(report).toBeVisible()
  for (const tile of ["Visitors", "Pageviews", "Signups"]) {
    await expect(
      report.getByRole("term").filter({ hasText: tile }),
    ).toBeVisible()
  }

  const window = page.getByRole("group", { name: "Window" })
  await expect(window.getByRole("button", { name: "30 days" })).toHaveAttribute(
    "aria-pressed",
    "true",
  )
  const week = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/analytics/report") &&
      new URL(r.url()).searchParams.get("days") === "7",
  )
  await window.getByRole("button", { name: "7 days" }).click()
  expect((await week).ok()).toBe(true)
  await expect(window.getByRole("button", { name: "7 days" })).toHaveAttribute(
    "aria-pressed",
    "true",
  )
  await expect(report).toBeVisible()
})

test.describe("not an admin", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("logged out, /admin redirects to login", async ({ page }) => {
    await page.goto("/admin")
    await page.waitForURL(/\/login/)
  })

  test("a reader sees admins only and no menu entry", async ({ page }) => {
    const email = randomEmail()
    await createUser({ email })
    await logInUser(page, email)

    await page.getByTestId("user-menu").click()
    await expect(page.getByRole("menuitem", { name: "Profile" })).toBeVisible()
    await expect(page.getByRole("menuitem", { name: "Analytics" })).toHaveCount(
      0,
    )

    await page.goto("/admin")
    await expect(page.getByText("Admins only.")).toBeVisible()
    await expect(page.getByTestId("analytics-report")).toHaveCount(0)
  })
})
