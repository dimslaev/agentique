import type { Page } from "@playwright/test"

/** Rail panels start folded except Stories; open them all as if the reader
 *  had, so a test can read their contents. */
export async function openAllPanels(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem(
      "agentique.rails.v2",
      JSON.stringify({
        open: {
          "who-wrote": true,
          voices: true,
          "reader-picks": true,
        },
      }),
    )
  })
}
