import { describe, expect, it } from 'vitest'
import { SCRATCH, isScribble, nothingLeft, scratchOut, tokens, wordsUnder } from './scratch.js'

// A back-and-forth path sampled every few pixels, as a pointer reports it.
const zigzag = (x0, x1, y, turns) => {
  const out = []
  for (let i = 0; i < turns; i++) {
    const [a, b] = i % 2 ? [x1, x0] : [x0, x1]
    for (let k = 0; k <= 10; k++) out.push({ x: a + ((b - a) * k) / 10, y: y + (i % 3) })
  }
  return out
}

describe('scratching words out', () => {
  it('replaces only the chosen words and keeps spacing and line breaks', () => {
    const text = 'my boss was horrible\nand I cried'
    const t = tokens(text)
    expect(scratchOut(text, [t.indexOf('horrible')])).toBe(`my boss was ${SCRATCH}\nand I cried`)
    expect(scratchOut(text, [t.indexOf('\n')])).toBe(text)                 // whitespace is never scratched
  })
  it('knows when nothing is left', () => {
    expect(nothingLeft(`${SCRATCH} ${SCRATCH}`)).toBe(true)
    expect(nothingLeft(`${SCRATCH} left`)).toBe(false)
  })
})

describe('telling a scribble from a click or a drag', () => {
  it('a back-and-forth scribble counts', () => {
    expect(isScribble(zigzag(10, 80, 20, 5))).toBe(true)
  })
  it('a straight drag, a click and a tiny wobble do not', () => {
    expect(isScribble([{ x: 10, y: 10 }, { x: 200, y: 12 }])).toBe(false)
    expect(isScribble([{ x: 10, y: 10 }])).toBe(false)
    expect(isScribble(zigzag(10, 12, 20, 6))).toBe(false)
  })
})

describe('which words a scribble covers', () => {
  const boxes = [
    { index: 0, left: 0, right: 40, top: 0, bottom: 30 },
    { index: 2, left: 50, right: 120, top: 0, bottom: 30 },
    { index: 0 + 4, left: 0, right: 60, top: 40, bottom: 70 },   // the next line
  ]
  it('takes the words under the ink on that line only', () => {
    expect(wordsUnder(zigzag(55, 115, 12, 5), boxes)).toEqual([2])
  })
  it('a scribble that only clips the edge of a word leaves it', () => {
    expect(wordsUnder(zigzag(36, 115, 12, 5), boxes)).toEqual([2])
  })
})
