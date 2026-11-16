import { forwardRef, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { freshAfter, segments } from './writing.js'

const INK_MS = 260          // how long one letter takes to be written
const STEP_MS = 32          // the gap between letters of a paste
const SETTLE_MS = 900       // fresh letters become plain text after this

/**
 * Writing that looks written: the textarea stays the real input (typing, pasting, selection, screen readers,
 * the keyboard all work as usual) but its letters are invisible; a mirror drawn over it shows each new letter
 * being drawn left to right in graphite, and a small pencil follows the caret, wobbling while you write.
 * With reduced motion the letters simply appear and the pencil stands still.
 */
const HandwritingArea = forwardRef(function HandwritingArea({ value, onChange, className = '', ...rest }, ref) {
  const [fresh, setFresh] = useState([])
  const [caret, setCaret] = useState(null)          // { x, y } of the caret in the mirror, when focused
  const [writing, setWriting] = useState(false)
  const prev = useRef(value)
  const area = useRef(null)
  const mark = useRef(null)
  const timers = useRef([])
  const [sel, setSel] = useState(value.length)

  // Letters typed or pasted (or changed from outside: cleared after saving) become fresh, then settle.
  useEffect(() => {
    if (prev.current === value) return
    const now = performance.now()
    setFresh(f => freshAfter(f, prev.current, value, now))
    prev.current = value
    setWriting(true)
    const t1 = setTimeout(() => setWriting(false), 450)
    const t2 = setTimeout(() => setFresh(f => f.filter(x => performance.now() - x.born < SETTLE_MS)), SETTLE_MS + 40 * Math.min(value.length, 60))
    timers.current.push(t1, t2)
  }, [value])
  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  // The pencil sits on the caret: measured from a marker placed at the caret in the mirror.
  useLayoutEffect(() => {
    if (!mark.current || document.activeElement !== area.current) { setCaret(null); return }
    setCaret({ x: mark.current.offsetLeft, y: mark.current.offsetTop })
  }, [value, sel, fresh])

  const setRefs = el => { area.current = el; if (typeof ref === 'function') ref(el); else if (ref) ref.current = el }
  const track = e => setSel(e.target.selectionStart ?? e.target.value.length)
  const parts = segments(value, fresh)
  const before = value.slice(0, sel)

  return (
    <div className={`handwriting ${writing ? 'is-writing' : ''}`}>
      <textarea ref={setRefs} className={`handwriting-input ${className}`} value={value}
                onChange={e => { onChange(e); track(e) }} onSelect={track} onKeyUp={track} onClick={track}
                onFocus={track} onBlur={() => setCaret(null)} {...rest} />
      <div className={`handwriting-ink ${className}`} aria-hidden="true">
        {parts.map((p, k) => (p.fresh
          ? <span key={k} className="ink-new" style={{ animationDelay: `${Math.min(p.fresh.order, 40) * STEP_MS}ms`, animationDuration: `${INK_MS}ms` }}>{p.text}</span>
          : <span key={k}>{p.text}</span>))}
        {value.endsWith('\n') ? ' ' : null}
      </div>
      {/* an invisible copy of the text up to the caret, ending in the marker the pencil is placed on */}
      <div className={`handwriting-ink handwriting-measure ${className}`} aria-hidden="true">
        {before}<span ref={mark} className="handwriting-mark">{'​'}</span>
      </div>
      {caret && (
        <svg className="pencil" style={{ transform: `translate(${caret.x - 5}px, ${caret.y - 8}px)` }} viewBox="0 0 40 40" aria-hidden="true">
          <g className="pencil-body">
            <path d="M6 34 L9 25 L30 4 L36 10 L15 31 Z" fill="var(--mk-butter-on)" stroke="var(--ink)" strokeWidth="1.6" strokeLinejoin="round" />
            <path d="M30 4 L36 10 L33 13 L27 7 Z" fill="var(--coral)" stroke="var(--ink)" strokeWidth="1.6" strokeLinejoin="round" />
            <path d="M6 34 L9 25 L15 31 Z" fill="var(--paper)" stroke="var(--ink)" strokeWidth="1.6" strokeLinejoin="round" />
            <path d="M6 34 L7.6 29.4 L10.6 32.4 Z" fill="var(--ink)" />
          </g>
        </svg>
      )}
    </div>
  )
})

export default HandwritingArea
