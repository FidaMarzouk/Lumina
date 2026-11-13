import { useEffect, useState } from 'react'
import { useMediaQuery } from './useMediaQuery'
import { usePersisted } from './usePersisted'

// The paper's tint by the person's own clock: brighter butter in the morning, the usual cream by day, warmer
// toward peach at dusk, and the night garden from 9pm to 7am.
export function paperFor(hour) {
  if (hour >= 21 || hour < 7) return 'night'
  if (hour < 10) return 'morning'
  if (hour < 17) return 'day'
  return 'dusk'
}

// How the person wants the app to look. Kept in this browser.
export const APPEARANCE = [
  { id: 'device', label: 'Follow my device', note: 'suggested', text: 'Matches your phone or computer’s own dark mode.' },
  { id: 'clock', label: 'Follow the clock', note: 'most Lumina', text: 'Night garden from 9pm to 7am, whatever the device says.' },
  { id: 'day', label: 'Day paper', note: 'always light', text: 'Cream all the time.' },
  { id: 'night', label: 'Night garden', note: 'always dark', text: 'For light-sensitive eyes, or anyone who prefers it.' },
]

/**
 * Sets <html data-paper="morning|day|dusk|night"> (the colours live in globals.css) from the person's choice:
 * follow the device's dark mode (the default), follow the clock, or always day / always night.
 * On day paper the cream still warms with the time of day.
 */
export function useAppearance() {
  const [choice, setChoice] = usePersisted('lumina.appearance', 'device')
  const deviceDark = useMediaQuery('(prefers-color-scheme: dark)')
  const [clock, setClock] = useState(() => paperFor(new Date().getHours()))
  useEffect(() => {
    const id = setInterval(() => setClock(paperFor(new Date().getHours())), 60_000)
    return () => clearInterval(id)
  }, [])

  const night = choice === 'night' || (choice === 'clock' && clock === 'night') || (choice === 'device' && deviceDark)
  const paper = night ? 'night' : clock === 'night' ? 'day' : clock
  useEffect(() => { document.documentElement.dataset.paper = paper }, [paper])
  return { paper, night, choice, setChoice }
}
