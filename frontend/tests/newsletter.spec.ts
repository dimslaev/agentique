import { expect, test } from "@playwright/test"
import { randomEmail } from "./utils/random"

test("Newsletter signup succeeds with a valid email", async ({ page }) => {
  await page.goto("/newsletter")

  await page.getByLabel("Email *").fill(randomEmail())
  await page.getByRole("button", { name: "Subscribe" }).click()

  await expect(page.getByText("You're subscribed.")).toBeVisible()
})

test("Newsletter signup shows inline error for invalid email", async ({
  page,
}) => {
  await page.goto("/newsletter")

  await page.getByLabel("Email *").fill("not-an-email")
  await page.getByRole("button", { name: "Subscribe" }).click()

  await expect(page.getByText("Valid email is required")).toBeVisible()
  await expect(page.getByText("You're subscribed.")).not.toBeVisible()
})
