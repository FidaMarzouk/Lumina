import { describe, expect, it } from 'vitest'
import { footpath, whereOnTrail } from './trail'

const journey = (status, stepIndex = 0) => ({ status, step_index: stepIndex, steps: [{}, {}, {}, {}] })

describe('whereOnTrail', () => {
  it('places the walker before, along and at the end of the trail', () => {
    expect(whereOnTrail(journey('not_started'))).toEqual({ here: -1, walked: 0, done: false })
    expect(whereOnTrail(journey('active', 2))).toEqual({ here: 2, walked: 2, done: false })
    expect(whereOnTrail(journey('paused', 1))).toEqual({ here: 1, walked: 1, done: false })
    expect(whereOnTrail(journey('completed', 4))).toEqual({ here: 3, walked: 4, done: true })
  })
})

describe('footpath', () => {
  const points = [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 200, y: 50 }]
  const path = footpath(points)

  it('passes through every point, measured along its length', () => {
    expect(path.d.startsWith('M 0.0 0.0 C')).toBe(true)
    expect(path.nodes).toHaveLength(points.length)
    expect(path.nodes[0]).toBe(0)
    expect(path.nodes[2]).toBeCloseTo(path.length, 6)
    for (let i = 0; i < points.length; i++) {
      const p = path.at(path.nodes[i])
      expect(p.x).toBeCloseTo(points[i].x, 0)
      expect(p.y).toBeCloseTo(points[i].y, 0)
    }
  })

  it('is at least as long as the straight lines between the points, and clamps outside the path', () => {
    expect(path.length).toBeGreaterThanOrEqual(100 + Math.hypot(100, 50) - 1e-6)
    expect(path.at(-10)).toEqual({ x: 0, y: 0 })
    const end = path.at(path.length + 10)
    expect(end.x).toBeCloseTo(200, 6)
    expect(end.y).toBeCloseTo(50, 6)
  })
})
