// How far along a journey's trail someone is: the landmark they are at (-1 before setting off),
// how many landmarks are behind them, and whether they have walked the whole way.
export function whereOnTrail(journey) {
  const n = journey.steps.length
  if (journey.status === 'completed') return { here: n - 1, walked: n, done: true }
  if (journey.status === 'not_started') return { here: -1, walked: 0, done: false }
  return { here: journey.step_index, walked: journey.step_index, done: false }
}

const bez = (a, b, c, d, t) => {
  const u = 1 - t
  return u * u * u * a + 3 * u * u * t * b + 3 * u * t * t * c + t * t * t * d
}

/**
 * A smooth footpath through `points` (Catmull-Rom, drawn as cubic Béziers), measured along its length:
 * `d` is the SVG path, `nodes[i]` the distance along the path at points[i], and `at(s)` the point at
 * distance s. Used to place landmarks and the walker without measuring the DOM.
 */
export function footpath(points) {
  const segs = []
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i], p1 = points[i], p2 = points[i + 1], p3 = points[i + 2] ?? p2
    segs.push([p1, { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 },
      { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 }, p2])
  }
  const f = v => v.toFixed(1)
  const d = `M ${f(points[0].x)} ${f(points[0].y)} `
    + segs.map(([, c1, c2, p2]) => `C ${f(c1.x)} ${f(c1.y)}, ${f(c2.x)} ${f(c2.y)}, ${f(p2.x)} ${f(p2.y)}`).join(' ')

  const samples = [{ ...points[0], s: 0 }]
  const nodes = [0]
  let s = 0
  segs.forEach(([p1, c1, c2, p2]) => {
    for (let k = 1; k <= 24; k++) {
      const t = k / 24
      const p = { x: bez(p1.x, c1.x, c2.x, p2.x, t), y: bez(p1.y, c1.y, c2.y, p2.y, t) }
      const prev = samples[samples.length - 1]
      s += Math.hypot(p.x - prev.x, p.y - prev.y)
      samples.push({ ...p, s })
    }
    nodes.push(s)
  })

  const at = dist => {
    const target = Math.max(0, Math.min(s, dist))
    const i = samples.findIndex(p => p.s >= target)
    if (i <= 0) return { x: samples[0].x, y: samples[0].y }
    const a = samples[i - 1], b = samples[i]
    const k = (target - a.s) / (b.s - a.s || 1)
    return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k }
  }
  return { d, length: s, nodes, at }
}
