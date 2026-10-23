import { useState } from "react"
import { trackEvent } from "@/shared/lib/analytics"
import { Button } from "@/shared/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog"

/** The Pro plan's call to action. Checkout isn't live, so it counts the
 *  click and says so. */
export function UpgradeButton() {
  const [dialogOpen, setDialogOpen] = useState(false)

  function onUpgrade() {
    trackEvent("checkout_click", {
      plan: "pro",
      price: 10,
      source: "developers",
    })
    setDialogOpen(true)
  }

  return (
    <>
      <Button onClick={onUpgrade}>Upgrade to Pro — $10/mo</Button>
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Coming soon</DialogTitle>
            <DialogDescription>
              The Pro API isn&apos;t live yet. We&apos;ll email you the moment
              it opens — thanks for the interest.
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    </>
  )
}
