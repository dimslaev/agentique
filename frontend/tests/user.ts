import { type APIRequestContext, expect, type Page } from "@playwright/test"
import { findLastEmail } from "./mailcatcher"

// Read the newest email to `email` from mailcatcher and pull out the sign-in
// link the backend put in it.
export async function signInLinkFor(request: APIRequestContext, email: string) {
  const message = await findLastEmail({
    request,
    filter: (e) => e.recipients.includes(`<${email}>`),
  })
  const response = await request.get(
    `${process.env.MAILCATCHER_HOST}/messages/${message.id}.html`,
  )
  const html = await response.text()
  const match = html.match(/href="([^"]*\/auth\?token=[^"]+)"/)
  if (!match) throw new Error(`No sign-in link in the email to ${email}`)
  return match[1]
}

export async function logInUser(
  page: Page,
  request: APIRequestContext,
  email: string,
) {
  await page.goto("/login")
  await page.getByTestId("email-input").fill(email)
  await page.getByRole("button", { name: "Email me a sign-in link" }).click()
  await expect(page.getByTestId("link-sent")).toBeVisible()

  await page.goto(await signInLinkFor(request, email))
  await page.waitForURL("/")
  await expect(page.getByTestId("user-menu")).toBeVisible()
}

export async function logOutUser(page: Page) {
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await page.goto("/login")
}
