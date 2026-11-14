import { describe, expect, it } from 'vitest'
import { CRISIS_COPY, LINES, moreUrgent } from './helpLines'

describe('crisis panel wording', () => {
  it('has wording for every crisis subtype the backend sends', () => {
    for (const subtype of ['ideation', 'method', 'third_party']) {
      expect(CRISIS_COPY[subtype].title).toBeTruthy()
      expect(CRISIS_COPY[subtype].text).toBeTruthy()
    }
  })

  it('never asks the person to declare they are safe', () => {
    for (const { title, text } of Object.values(CRISIS_COPY)) {
      expect(`${title} ${text}`.toLowerCase()).not.toMatch(/i'm safe|i am safe|confirm/)
    }
  })

  it('keeps phone numbers in the lines only, never in the wording', () => {
    for (const { title, text } of Object.values(CRISIS_COPY)) expect(`${title} ${text}`).not.toMatch(/\d/)
    for (const line of LINES) expect(line.tel).toMatch(/^\d+$/)
  })
})

describe('moreUrgent', () => {
  it('keeps the most urgent wording across a conversation', () => {
    expect(moreUrgent(null, 'third_party')).toBe('third_party')
    expect(moreUrgent('third_party', 'ideation')).toBe('ideation')
    expect(moreUrgent('ideation', 'method')).toBe('method')
    expect(moreUrgent('method', 'ideation')).toBe('method')
    expect(moreUrgent('ideation', 'third_party')).toBe('ideation')
  })

  it('ignores an unknown subtype', () => {
    expect(moreUrgent('ideation', 'none')).toBe('ideation')
  })
})
