import { test as setup } from "@playwright/test"
import { firstSuperuser } from "./config.ts"
import { logInUser } from "./user.ts"

const authFile = "playwright/.auth/user.json"

setup("authenticate", async ({ page }) => {
  await logInUser(page, firstSuperuser)
  await page.context().storageState({ path: authFile })
})
