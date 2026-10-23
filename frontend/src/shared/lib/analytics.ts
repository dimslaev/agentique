/**
 * First-party analytics tracker. Posts pageviews / events to our own FastAPI
 * backend (`/api/v1/analytics/collect`). No third party, no dashboard —
 * query the `analytics_event` table directly.
 *
 * Works for logged-out visitors: the auth header is only attached when a token
 * exists, and the backend records the event anonymously otherwise.
 * Fire-and-forget: any failure is swallowed so analytics can never break the app.
 */
const ENDPOINT = `${import.meta.env.VITE_API_URL}/api/v1/analytics/collect`
const VISITOR_KEY = "analytics_visitor_id"

function getVisitorId(): string {
  try {
    let id = localStorage.getItem(VISITOR_KEY)
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem(VISITOR_KEY, id)
    }
    return id
  } catch {
    // localStorage blocked (private mode etc.) — fall back to a per-load id
    return crypto.randomUUID()
  }
}

type EventBody = {
  event: string
  path?: string
  referrer?: string
  visitor_id: string
  props?: Record<string, unknown>
}

function send(body: EventBody): void {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  }
  // Attach identity only if the visitor is signed in; anonymous otherwise.
  const token = localStorage.getItem("access_token")
  if (token) headers.Authorization = `Bearer ${token}`

  void fetch(ENDPOINT, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    keepalive: true, // survive navigation / tab close
  }).catch(() => {})
}

let lastPageview: { path: string; at: number } | null = null
// `document.referrer` is whatever loaded the app and doesn't change on in-app
// navigation, so only the first pageview of a load carries it. Otherwise one
// Google visit would count as a Google referral on every page after it.
let referrerSent = false

export function trackPageview(path: string): void {
  // The pageview is fired from the router's `onResolved` subscription (module
  // scope), so React re-renders and StrictMode can't trigger it. This guard is
  // belt-and-suspenders: drop an identical pageview fired within 500ms (dev HMR
  // re-registering the subscription, a duplicate onResolved). Genuine
  // re-navigations to the same path are far enough apart to still count.
  const now = Date.now()
  if (lastPageview?.path === path && now - lastPageview.at < 500) return
  lastPageview = { path, at: now }
  const referrer = referrerSent ? undefined : document.referrer || undefined
  referrerSent = true

  send({
    event: "pageview",
    path,
    referrer,
    visitor_id: getVisitorId(),
  })
}

export function trackEvent(
  event: string,
  props?: Record<string, unknown>,
): void {
  send({
    event,
    path: window.location.pathname,
    visitor_id: getVisitorId(),
    props,
  })
}

/** Handlers for an outbound article link. A middle-click into a background
 *  tab fires `auxclick`, never `click`, so both are tracked. */
export function articleClickHandlers(
  article: { id: number; score: number },
  props?: Record<string, unknown>,
) {
  const track = () =>
    trackEvent("article_click", {
      article_id: article.id,
      score: article.score,
      ...props,
    })
  return {
    onClick: track,
    onAuxClick: (e: { button: number }) => {
      if (e.button === 1) track()
    },
  }
}
