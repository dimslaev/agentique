import { test as setup } from "@playwright/test"
import { firstSuperuser } from "./config.ts"
import { logInUser } from "./user.ts"

const authFile = "playwright/.auth/user.json"

setup("authenticate", async ({ page, request }) => {
  await logInUser(page, request, firstSuperuser)
  await page.context().storageState({ path: authFile })
})
