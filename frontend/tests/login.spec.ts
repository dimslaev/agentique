import { expect, test } from "@playwright/test"
import { firstSuperuser } from "./config.ts"
import { randomEmail } from "./random.ts"
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

// Each link request replaces the user's token, so two tests asking for the
// same user's link at once would break each other's.
test.describe("superuser", () => {
  test.describe.configure({ mode: "serial" })

  test("Log in with the emailed link", async ({ page }) => {
    await logInUser(page, firstSuperuser)
  })

  test("The same link works again after logging out", async ({ page }) => {
    await logInUser(page, firstSuperuser)
    const link = signInLinkFor(firstSuperuser)
    await logOutUser(page)

    await page.goto(link)
    await page.waitForURL("/")
    await expect(page.getByTestId("user-menu")).toBeVisible()
  })
})

test("Log in with invalid email", async ({ page }) => {
  await page.goto("/login")

  await page.getByTestId("email-input").fill("invalidemail")
  await page.getByRole("button", { name: "Email me a sign-in link" }).click()

  await expect(page.getByText("Invalid email address")).toBeVisible()
})

test("An unknown email gets an account and a link", async ({ page }) => {
  await logInUser(page, randomEmail())
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

test("Sign-in pages keep the site header and footer", async ({ page }) => {
  for (const path of ["/login", "/auth?token=bad"]) {
    await page.goto(path)
    await expect(
      page.getByRole("banner").getByRole("link", { name: "agentique" }),
    ).toBeVisible()
    // The dev server adds the router devtools' own footer.
    await expect(
      page.getByRole("contentinfo").filter({ hasNotText: "TanStack" }),
    ).toBeVisible()
  }
})
