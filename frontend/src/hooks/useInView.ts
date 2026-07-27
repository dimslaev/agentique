import { useEffect, useRef, useState } from "react"

/**
 * Reports when an element first comes within `rootMargin` of the viewport,
 * then stays true for good.
 *
 * Latching matters: the landing-page boxes gate their queries on this, and a
 * box that flipped back to false on scroll-away would drop its data and
 * refetch the entire grid on the way back up.
 */
export function useInView<T extends HTMLElement>(rootMargin = "200px") {
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    if (inView) return
    const el = ref.current
    if (!el) return

    // No observer (older browsers, jsdom): show everything rather than
    // leaving the page permanently blank.
    if (typeof IntersectionObserver === "undefined") {
      setInView(true)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setInView(true)
      },
      { rootMargin },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [inView, rootMargin])

  return { ref, inView }
}
