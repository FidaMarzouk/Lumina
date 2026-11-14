import { describe, expect, it } from 'vitest'
import { paperFor } from './useDaylight'

describe('paperFor', () => {
  it('follows the clock: night garden from 9pm to 7am', () => {
    expect([21, 23, 0, 6].map(paperFor)).toEqual(['night', 'night', 'night', 'night'])
    expect(paperFor(7)).toBe('morning')
    expect(paperFor(9)).toBe('morning')
    expect(paperFor(10)).toBe('day')
    expect(paperFor(16)).toBe('day')
    expect(paperFor(17)).toBe('dusk')
    expect(paperFor(20)).toBe('dusk')
  })
})
