import { describe, expect, it } from 'vitest'
import { latestLoop } from './loop'

const entry = (id, chain) => ({ id, evidence: chain ? { chain } : {} })

describe('latestLoop', () => {
  it('finds the most recent link with at least three parts, in order', () => {
    const entries = [
      entry('old', { situation: 'deadline', thought: 'I will fail', feeling: 'anxious' }),
      entry('new', { feeling: 'hurt', behaviour: 'went quiet', thought: 'they are annoyed' }),
      entry('thin', { feeling: 'tired' }),
    ]
    const loop = latestLoop(entries)
    expect(loop.entry.id).toBe('new')
    expect(loop.steps.map(s => s.key)).toEqual(['thought', 'feeling', 'behaviour'])
    expect(loop.steps[0]).toEqual({ key: 'thought', label: 'You thought', text: 'they are annoyed' })
  })

  it('returns null when no entry has enough of the link', () => {
    expect(latestLoop([entry('a', { feeling: 'sad', behaviour: 'stayed in' }), entry('b', null)])).toBeNull()
    expect(latestLoop([])).toBeNull()
  })
})
