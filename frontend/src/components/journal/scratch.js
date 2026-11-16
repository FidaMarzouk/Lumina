// Scratching words out of a journal entry: pure helpers (tested without a browser).

// Where a word was scratched out; the page draws a scribble there. Matches lumina/memory/store.py SCRATCH.
export const SCRATCH = ''

// Words and the whitespace between them, in order, so the text can be put back together exactly.
export const tokens = text => text.split(/(\s+)/).filter(t => t !== '')
export const isWord = t => !/^\s+$/.test(t)

// The text with the words at `indexes` (token positions) replaced by a scratch mark.
export function scratchOut(text, indexes) {
  const set = new Set(indexes)
  return tokens(text).map((t, i) => (set.has(i) && isWord(t) && t !== SCRATCH ? SCRATCH : t)).join('')
}

export const nothingLeft = text => tokens(text).every(t => !isWord(t) || t === SCRATCH)

/**
 * Is this pointer path a scratch-out? A scribble goes back and forth: at least `minTurns` changes of horizontal
 * direction, each stroke longer than `jitter` px, and enough ink overall. A click, a tap or a straight drag is not.
 */
export function isScribble(points, { minTurns = 2, jitter = 4, minLength = 36 } = {}) {
  let turns = 0, dir = 0, length = 0, run = 0
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x
    length += Math.hypot(dx, points[i].y - points[i - 1].y)
    if (Math.abs(dx) < 0.5) continue
    const d = Math.sign(dx)
    if (d === dir || dir === 0) { run += Math.abs(dx); dir = d; continue }
    if (run >= jitter) turns++
    dir = d
    run = Math.abs(dx)
  }
  return turns >= minTurns && length >= minLength
}

/**
 * Which words the scribble went over: a word is scratched when points of the path fall on it across at least
 * `cover` of its width (or it is narrow and the path crossed it). `boxes`: [{ index, left, right, top, bottom }].
 */
export function wordsUnder(points, boxes, { cover = 0.4, slack = 5 } = {}) {
  return boxes.filter(b => {
    const on = points.filter(p => p.x >= b.left - slack && p.x <= b.right + slack && p.y >= b.top - slack && p.y <= b.bottom + slack)
    if (on.length === 0) return false
    const xs = on.map(p => Math.min(b.right, Math.max(b.left, p.x)))
    const span = Math.max(...xs) - Math.min(...xs)
    return span >= cover * (b.right - b.left) || (b.right - b.left < 28 && on.length >= 2)
  }).map(b => b.index)
}

// A scribble to draw where a word was: a coil of tight, slanted loops travelling across the word, like a pen
// scratching something out. The same every time for the same place (seeded by position).
export function scribblePath(seed, width = 48, height = 20) {
  let s = (seed * 9301 + 49297) % 233280
  const rnd = () => (s = (s * 9301 + 49297) % 233280) / 233280
  const loops = 6 + Math.floor(rnd() * 3)
  const step = (width - 6) / loops
  let x = 3, d = `M${x} ${height * 0.6}`
  for (let i = 0; i < loops; i++) {
    const top = 1 + rnd() * 3, bottom = height - 1 - rnd() * 3
    // up and forward, then back down a little behind: each loop overlaps the last
    d += ` C${(x + step * 1.4).toFixed(1)} ${top.toFixed(1)}, ${(x + step * 1.9).toFixed(1)} ${(top + 2).toFixed(1)}, ${(x + step * 1.2).toFixed(1)} ${(height / 2).toFixed(1)}`
    d += ` S${(x + step * 0.2).toFixed(1)} ${bottom.toFixed(1)}, ${(x + step).toFixed(1)} ${(bottom - 2).toFixed(1)}`
    x += step
  }
  return d
}
