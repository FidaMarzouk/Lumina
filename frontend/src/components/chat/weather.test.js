import { describe, expect, it } from 'vitest'
import { withWeather } from './weather'

const OPENING = "Welcome back, Sam. How are you feeling today?"

describe('withWeather', () => {
  it('leaves the opening alone without a check-in', () => {
    expect(withWeather(OPENING, null)).toBe(OPENING)
    expect(withWeather(OPENING, 'unknown')).toBe(OPENING)
  })

  it('does not ask how they feel again on a light day', () => {
    const out = withWeather(OPENING, 'clear')
    expect(out).toBe("Welcome back, Sam. Sounds like a lighter day. What's on your mind?")
  })

  it('sets the suggested agenda aside on a heavy day', () => {
    const opening = 'Welcome back, Sam. You could pick up where we left off with “Map your nights”.'
    expect(withWeather(opening, 'storm')).toBe(
      "Welcome back, Sam. That sounds like a lot. Let's slow down first: one long breath out with me, then we'll talk.")
  })

  it('keeps a guided step the person chose, even on a heavy day', () => {
    const opening = 'Welcome back, Sam. Today’s step: Map your nights.'
    const out = withWeather(opening, 'rain', true)
    expect(out.startsWith('Welcome back, Sam. I\'m glad you came.')).toBe(true)
    expect(out.endsWith('Today’s step: Map your nights.')).toBe(true)
  })
})
