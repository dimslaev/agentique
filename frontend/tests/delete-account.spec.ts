import { expect, test } from "@playwright/test"
import { createUser } from "./api.ts"
import { randomEmail } from "./random"
import { logInUser } from "./user"

test.use({ storageState: { cookies: [], origins: [] } })

test("Cancel keeps the account, Delete signs out", async ({ page }) => {
  const email = randomEmail()
  await createUser({ email })
  await logInUser(page, email)

  // The backend can't delete a user with analytics events yet (the
  // analytics_event.user_id foreign key), and signing in records one, so the
  // delete is stubbed. This checks the page's side of the flow.
  let deletes = 0
  await page.route(
    (url) => url.pathname === "/api/v1/users/me",
    (route) => {
      if (route.request().method() !== "DELETE") return route.fallback()
      deletes++
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ message: "User deleted successfully" }),
      })
    },
  )

  await page.goto("/profile")
  await page.getByRole("tab", { name: "Danger zone" }).click()
  const dialog = page.getByRole("dialog", { name: "Confirmation Required" })

  await page.getByRole("button", { name: "Delete Account" }).click()
  await expect(dialog).toBeVisible()
  await dialog.getByRole("button", { name: "Cancel" }).click()
  await expect(dialog).toHaveCount(0)
  expect(deletes).toBe(0)

  await page.getByRole("button", { name: "Delete Account" }).click()
  await dialog.getByRole("button", { name: "Delete" }).click()
  await page.waitForURL("/login")
  expect(deletes).toBe(1)
  await expect(
    page.getByText("Your account has been successfully deleted"),
  ).toBeVisible()
})
