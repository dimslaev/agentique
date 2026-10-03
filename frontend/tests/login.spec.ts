import { expect, test } from "@playwright/test"
import { firstSuperuser } from "./config.ts"
import { logInUser, logOutUser, signInLinkFor } from "./user.ts"

test.use({ storageState: { cookies: [], origins: [] } })

test("Email input is visible, empty and editable", async ({ page }) => {
  await page.goto("/login")

  const input = page.getByTestId("email-input")
  await expect(input).toBeVisible()
  await expect(input).toHaveText("")
  await expect(input).toBeEditable()
})

test("There is no password field", async ({ page }) => {
  await page.goto("/login")

  await expect(page.getByLabel("Password")).toHaveCount(0)
})

test("Log in with the emailed link", async ({ page, request }) => {
  await logInUser(page, request, firstSuperuser)
})

test("The same link works again after logging out", async ({
  page,
  request,
}) => {
  await logInUser(page, request, firstSuperuser)
  const link = await signInLinkFor(request, firstSuperuser)
  await logOutUser(page)

  await page.goto(link)
  await page.waitForURL("/")
  await expect(page.getByTestId("user-menu")).toBeVisible()
})

test("Log in with invalid email", async ({ page }) => {
  await page.goto("/login")

  await page.getByTestId("email-input").fill("invalidemail")
  await page.getByRole("button", { name: "Email me a sign-in link" }).click()

  await expect(page.getByText("Invalid email address")).toBeVisible()
})

test("Unknown email gets the same answer", async ({ page }) => {
  await page.goto("/login")

  await page.getByTestId("email-input").fill("nobody@example.com")
  await page.getByRole("button", { name: "Email me a sign-in link" }).click()

  await expect(page.getByTestId("link-sent")).toBeVisible()
})

test("A bad link says so", async ({ page }) => {
  await page.goto("/auth?token=nope")

  await expect(page.getByText("This link doesn't work")).toBeVisible()
})

test("Redirects to /login when token is wrong", async ({ page }) => {
  await page.goto("/profile")
  await page.evaluate(() => {
    localStorage.setItem("access_token", "invalid_token")
  })
  await page.goto("/profile")
  await expect(page).toHaveURL(/\/login/)
})
