import { useEffect, useState } from 'react'
import { usePersisted } from './usePersisted'

// The paper follows the person's own clock: brighter butter in the morning, the usual cream by day, warmer
// toward peach at dusk, and forest-green night paper with cream ink after 10pm (night mode).
export function paperFor(hour) {
  if (hour >= 22 || hour < 5) return 'night'
  if (hour < 10) return 'morning'
  if (hour < 17) return 'day'
  return 'dusk'
}

/**
 * Sets <html data-paper="…"> (the colours live in globals.css). Night mode follows the clock until the person
 * turns it on or off themselves; their choice is remembered, and toggling back to what the clock would show
 * hands it back to the clock.
 */
export function useDaylight() {
  const [clock, setClock] = useState(() => paperFor(new Date().getHours()))
  const [choice, setChoice] = usePersisted('lumina.night', null)      // null = follow the clock
  useEffect(() => {
    const id = setInterval(() => setClock(paperFor(new Date().getHours())), 60_000)
    return () => clearInterval(id)
  }, [])

  const clockNight = clock === 'night'
  const night = choice ?? clockNight
  const paper = night ? 'night' : clockNight ? 'day' : clock
  useEffect(() => { document.documentElement.dataset.paper = paper }, [paper])

  const toggleNight = () => {
    const next = !night
    setChoice(next === clockNight ? null : next)
  }
  return { paper, night, toggleNight }
}
