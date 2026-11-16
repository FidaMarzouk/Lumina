import { describe, expect, it } from 'vitest'
import { diff, freshAfter, segments } from './writing.js'

describe('following what was just written', () => {
  it('finds the edit', () => {
    expect(diff('I walked', 'I walked home')).toEqual({ at: 8, removed: 0, inserted: 5 })
    expect(diff('I walked home', 'I home')).toEqual({ at: 2, removed: 7, inserted: 0 })
    expect(diff('abc', 'aXc')).toEqual({ at: 1, removed: 1, inserted: 1 })
  })
  it('marks typed letters, never spaces, and orders a paste so it is written out in turn', () => {
    const f = freshAfter([], '', 'hi you', 100)
    expect(f.map(x => x.i)).toEqual([0, 1, 3, 4, 5])
    expect(f.map(x => x.order)).toEqual([0, 1, 3, 4, 5])
  })
  it('keeps earlier fresh letters in place when typing in the middle, and drops deleted ones', () => {
    let f = freshAfter([], 'ab', 'abc', 1)                      // c is fresh at 2
    f = freshAfter(f, 'abc', 'aXbc', 2)                          // X inserted at 1: c moves to 3
    expect(f.map(x => x.i)).toEqual([1, 3])
    f = freshAfter(f, 'aXbc', 'ac', 3)                            // X and b deleted
    expect(f.map(x => x.i)).toEqual([1])
  })
  it('cuts the text into plain runs and fresh letters', () => {
    const f = [{ i: 2, born: 0, order: 0 }]
    expect(segments('abcd', f).map(s => s.text)).toEqual(['ab', 'c', 'd'])
  })
})
