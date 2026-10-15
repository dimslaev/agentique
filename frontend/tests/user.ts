import { execFileSync } from "node:child_process"
import { expect, type Page } from "@playwright/test"

const DB_CONTAINER = process.env.DB_CONTAINER ?? "agentique-db-1"

// The sign-in link for `email`, built from the token the backend stored for
// it. Each request replaces the token, so this is always the newest link.
// Reads the local db container rather than an inbox: no mail server needed.
export function signInLinkFor(email: string) {
  const query = `select login_token from "user" where email = '${email.replace(/'/g, "''")}'`
  const token = execFileSync("docker", [
    "exec",
    DB_CONTAINER,
    "sh",
    "-c",
    `psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"`,
    "sh",
    query,
  ])
    .toString()
    .trim()
  if (!token) throw new Error(`No sign-in link for ${email}`)
  return `/auth?token=${token}`
}

export async function logInUser(page: Page, email: string) {
  await page.goto("/login")
  await page.getByTestId("email-input").fill(email)
  await page.getByRole("button", { name: "Email me a sign-in link" }).click()
  await expect(page.getByTestId("link-sent")).toBeVisible()

  await page.goto(signInLinkFor(email))
  await page.waitForURL("/")
  await expect(page.getByTestId("user-menu")).toBeVisible()
}

export async function logOutUser(page: Page) {
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await page.goto("/login")
}
