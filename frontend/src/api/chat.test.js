import { describe, expect, it } from 'vitest'
import { splitLines } from './chat'

describe('splitLines (newline-delimited JSON from /chat/stream)', () => {
  it('returns complete lines and keeps the unfinished rest', () => {
    expect(splitLines('{"a":1}\n{"b":')).toEqual([['{"a":1}'], '{"b":'])
    expect(splitLines('{"a":1}\n{"b":2}\n')).toEqual([['{"a":1}', '{"b":2}'], ''])
  })

  it('skips blank lines and waits for a line with no newline yet', () => {
    expect(splitLines('\n\n{"a":1}\n')).toEqual([['{"a":1}'], ''])
    expect(splitLines('{"partial"')).toEqual([[], '{"partial"'])
  })
})
