import { expect, test } from "@playwright/test"
import { createUser } from "./api.ts"
import { randomEmail } from "./random"
import { logInUser } from "./user"

const tabs = ["Liked", "My profile", "Danger zone"]

test("My profile tab can be selected", async ({ page }) => {
  await page.goto("/profile")
  await page.getByRole("tab", { name: "My profile" }).click()
  await expect(page.getByRole("tab", { name: "My profile" })).toHaveAttribute(
    "aria-selected",
    "true",
  )
})

test("All tabs are visible", async ({ page }) => {
  await page.goto("/profile")
  for (const tab of tabs) {
    await expect(page.getByRole("tab", { name: tab })).toBeVisible()
  }
})

test.describe("Edit user profile", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  let email: string

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email })
  })

  test.beforeEach(async ({ page }) => {
    await logInUser(page, email)
    await page.goto("/profile")
    await page.getByRole("tab", { name: "My profile" }).click()
  })

  test("Save is disabled until something changes", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Save" })).toBeDisabled()
    await page.getByLabel("Full name").fill("Test User")
    await expect(page.getByRole("button", { name: "Save" })).toBeEnabled()
  })

  test("Save user name with a valid name", async ({ page }) => {
    const updatedName = "Test User 2"

    await page.getByLabel("Full name").fill(updatedName)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(page.getByLabel("Full name")).toHaveValue(updatedName)
  })

  test("Save company", async ({ page }) => {
    const company = "Acme Inc"

    await page.getByLabel("Company").fill(company)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(page.getByLabel("Company")).toHaveValue(company)
  })

  test("Edit user email with an invalid email shows error", async ({
    page,
  }) => {
    await page.getByLabel("Email").fill("")
    await page.getByLabel("Email").press("Tab")

    await expect(page.getByText("Invalid email address")).toBeVisible()
  })
})

test.describe("Edit user email", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Edit user email with a valid email", async ({ page }) => {
    const email = randomEmail()
    const updatedEmail = randomEmail()

    await createUser({ email })
    await logInUser(page, email)
    await page.goto("/profile")
    await page.getByRole("tab", { name: "My profile" }).click()

    await page.getByLabel("Email").fill(updatedEmail)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(page.getByLabel("Email")).toHaveValue(updatedEmail)
  })
})
