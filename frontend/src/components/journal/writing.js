// Which letters were just written, so the page can show them being drawn (HandwritingArea.jsx).

// Where `prev` and `next` differ: the edit is a run of `removed` letters at `at` replaced by `inserted` letters.
export function diff(prev, next) {
  let at = 0
  while (at < prev.length && at < next.length && prev[at] === next[at]) at++
  let tail = 0
  while (tail < prev.length - at && tail < next.length - at && prev[prev.length - 1 - tail] === next[next.length - 1 - tail]) tail++
  return { at, removed: prev.length - at - tail, inserted: next.length - at - tail }
}

/**
 * The fresh letters after an edit: [{ i, born, order }] by position. Letters already fresh keep their place
 * (shifted past the edit); letters inside a deleted run go; newly inserted letters are added, `order` counting
 * across the run so a paste is written out one letter after another.
 */
export function freshAfter(fresh, prev, next, now) {
  const { at, removed, inserted } = diff(prev, next)
  const kept = []
  for (const f of fresh) {
    if (f.i < at) kept.push(f)
    else if (f.i >= at + removed) kept.push({ ...f, i: f.i - removed + inserted })
  }
  for (let k = 0; k < inserted; k++) {
    if (!/\s/.test(next[at + k])) kept.push({ i: at + k, born: now, order: k })
  }
  return kept.sort((a, b) => a.i - b.i)
}

// The text cut into plain runs and single fresh letters, ready to draw.
export function segments(text, fresh) {
  const out = []
  let from = 0
  for (const f of fresh) {
    if (f.i >= text.length) break
    if (f.i > from) out.push({ text: text.slice(from, f.i) })
    out.push({ text: text[f.i], fresh: f })
    from = f.i + 1
  }
  if (from < text.length) out.push({ text: text.slice(from) })
  return out
}
