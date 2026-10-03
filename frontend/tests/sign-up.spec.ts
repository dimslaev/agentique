import { expect, test } from "@playwright/test"

import { randomEmail } from "./random"
import { signInLinkFor } from "./user"

test.use({ storageState: { cookies: [], origins: [] } })

test("Only an email is asked for", async ({ page }) => {
  await page.goto("/signup")

  await expect(page.getByTestId("email-input")).toBeEditable()
  await expect(page.getByLabel("Password")).toHaveCount(0)
  await expect(page.getByLabel("Full Name")).toHaveCount(0)
})

test("Sign up, then sign in from the welcome email", async ({
  page,
  request,
}) => {
  const email = randomEmail()

  await page.goto("/signup")
  await page.getByTestId("email-input").fill(email)
  await page.getByRole("button", { name: "Sign up" }).click()
  await expect(page.getByTestId("link-sent")).toBeVisible()

  await page.goto(await signInLinkFor(request, email))
  await page.waitForURL("/")
  await expect(page.getByTestId("user-menu")).toBeVisible()
})

test("Sign up from the feed", async ({ page }) => {
  await page.goto("/")
  await page.getByLabel("Email address").fill(randomEmail())
  await page.getByRole("button", { name: "Sign up" }).click()

  await expect(
    page.getByText("Check your inbox for your sign-in link."),
  ).toBeVisible()
})

test("Signing up twice gives the same answer", async ({ page }) => {
  const email = randomEmail()

  for (let i = 0; i < 2; i++) {
    await page.goto("/signup")
    await page.getByTestId("email-input").fill(email)
    await page.getByRole("button", { name: "Sign up" }).click()
    await expect(page.getByTestId("link-sent")).toBeVisible()
  }
})

test("Sign up with invalid email", async ({ page }) => {
  await page.goto("/signup")

  await page.getByTestId("email-input").fill("invalid-email")
  await page.getByRole("button", { name: "Sign up" }).click()

  await expect(page.getByText("Invalid email address")).toBeVisible()
})
