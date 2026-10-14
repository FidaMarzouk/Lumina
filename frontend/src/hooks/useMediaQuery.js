import { useSyncExternalStore } from 'react'

// True while the CSS media query matches (kept in sync as the window resizes).
export function useMediaQuery(query) {
  return useSyncExternalStore(
    notify => {
      const m = window.matchMedia(query)
      m.addEventListener('change', notify)
      return () => m.removeEventListener('change', notify)
    },
    () => window.matchMedia(query).matches,
    () => false,
  )
}
