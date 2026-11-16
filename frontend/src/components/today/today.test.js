import { describe, expect, it } from 'vitest'
import { daysAgo, hoursWord, moodSentence, nights, sleepSentence, todaysPick } from './today.js'

describe('the sleep tally', () => {
  it('lays out the last fourteen nights, oldest first, with gaps where nothing was logged', () => {
    const rows = nights([{ id: 'a', night: daysAgo(1), hours: 5, quality: 'poor' }], 14)
    expect(rows).toHaveLength(14)
    expect(rows[13]).toMatchObject({ night: daysAgo(1), hours: 5, quality: 'poor', id: 'a' })
    expect(rows[0].hours).toBeNull()
  })
  it('writes hours the way a person would', () => {
    expect(hoursWord(5.5)).toBe('5½')
    expect(hoursWord(6.8)).toBe('7')
    expect(hoursWord(7)).toBe('7')
  })
  it('says when this week is shorter than the week before', () => {
    const rows = nights([...Array.from({ length: 5 }, (_, i) => ({ night: daysAgo(14 - i), hours: 7 })),
                         ...Array.from({ length: 5 }, (_, i) => ({ night: daysAgo(5 - i), hours: 5 }))])
    expect(sleepSentence(rows)).toBe('about 6 hours a night, shorter this week')
    expect(sleepSentence(nights([]))).toMatch(/Nothing logged/)
  })
})

describe('the week in moods', () => {
  it('reads the stamps as one line', () => {
    expect(moodSentence([{ weather: 'rain' }, { weather: 'rain' }, { weather: 'clear' }])).toBe('a rainy week, with one clear day')
    expect(moodSentence([{ weather: 'fog' }, { weather: 'fog' }])).toBe('a foggy week')
    expect(moodSentence([])).toMatch(/No inner weather/)
  })
})

describe("today's pick from the jar", () => {
  it('is the same all day and changes from day to day', () => {
    const items = ['a', 'b', 'c']
    expect(todaysPick(items, '2026-11-16')).toBe(todaysPick(items, '2026-11-16'))
    expect(new Set(['2026-11-16', '2026-11-17', '2026-11-18'].map(d => todaysPick(items, d))).size).toBeGreaterThan(1)
    expect(todaysPick([], '2026-11-16')).toBeNull()
  })
})
