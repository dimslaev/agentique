import { expect, type Page, test } from "@playwright/test"

import { randomEmail } from "./random"
import { signInLinkFor } from "./user"

test.use({ storageState: { cookies: [], origins: [] } })

async function signUpFromFeed(page: Page, email: string) {
  await page.goto("/")
  await page.getByLabel("Email address").fill(email)
  await page.getByRole("button", { name: "Sign up" }).click()
  await expect(page.getByText("Check your inbox")).toBeVisible()
}

test("There is no sign up page", async ({ page }) => {
  await page.goto("/login")

  await expect(page.getByRole("link", { name: "Sign up" })).toHaveCount(0)
})

test("Sign up from the feed, then sign in from the welcome email", async ({
  page,
  request,
}) => {
  const email = randomEmail()

  await signUpFromFeed(page, email)

  await page.goto(await signInLinkFor(request, email))
  await page.waitForURL("/")
  await expect(page.getByTestId("user-menu")).toBeVisible()
})

test("Signing up twice gives the same answer", async ({ page }) => {
  const email = randomEmail()

  for (let i = 0; i < 2; i++) {
    await signUpFromFeed(page, email)
  }
})
